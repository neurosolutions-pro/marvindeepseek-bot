#!/usr/bin/env python3
"""
Hermes OpenAI-compatible integration gateway.

Primary mode (default): thin OpenAI-compatible proxy on host:port from
hermes.config.yaml, forwarding to an upstream OpenAI-compatible model
(local_upstream / Ollama / vLLM / cloud).

Optional mode HERMES_USE_NATIVE_GATEWAY=1: expect native `hermes gateway`
API server (NousResearch hermes-agent) and only health-check it.

This process is what MarvinDeepSeekBot (bot_client.py) talks to.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import uvicorn
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

logger = logging.getLogger("hermes_gateway")

CONFIG_PATH = Path(os.getenv("HERMES_CONFIG", str(ROOT / "hermes.config.yaml")))


def _load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise RuntimeError(f"Invalid config structure in {CONFIG_PATH}")
        return data
    return {}


CFG = _load_config()
HOST = str(CFG.get("host") or os.getenv("HERMES_HOST", "0.0.0.0"))
PORT = int(CFG.get("port") or os.getenv("HERMES_PORT", "8000"))
MODEL = str(CFG.get("model") or os.getenv("HERMES_MODEL", "hermes-local-mock"))
LOG_LEVEL = str(CFG.get("log_level") or os.getenv("HERMES_LOG_LEVEL", "info")).lower()
API_KEY = os.getenv("HERMES_API_KEY") or str(CFG.get("api_key") or "")
UPSTREAM_BASE_URL = (
    os.getenv("HERMES_UPSTREAM_BASE_URL")
    or str(CFG.get("upstream_base_url") or "http://127.0.0.1:8001/v1")
).rstrip("/")
UPSTREAM_API_KEY = os.getenv("HERMES_UPSTREAM_API_KEY") or os.getenv(
    "UPSTREAM_API_KEY", "local-upstream-key"
)
REQUEST_TIMEOUT = float(os.getenv("HERMES_TIMEOUT", "120"))

app = FastAPI(title="Hermes Integration Gateway", version="1.0.0")


def _require_auth(authorization: str | None) -> None:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="HERMES_API_KEY is not configured")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token.strip() != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health() -> dict[str, Any]:
    upstream_ok = False
    upstream_error = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Prefer upstream /health; fall back to /v1/models
            root = UPSTREAM_BASE_URL[:-3] if UPSTREAM_BASE_URL.endswith("/v1") else UPSTREAM_BASE_URL
            r = await client.get(f"{root.rstrip('/')}/health")
            if r.status_code >= 400:
                r = await client.get(
                    f"{UPSTREAM_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {UPSTREAM_API_KEY}"},
                )
            upstream_ok = r.status_code < 500
    except Exception as exc:  # noqa: BLE001 — surface in health payload
        upstream_error = str(exc)
    status = "ok" if upstream_ok else "degraded"
    return {
        "status": status,
        "service": "hermes-integration-gateway",
        "model": MODEL,
        "port": PORT,
        "upstream_base_url": UPSTREAM_BASE_URL,
        "upstream_ok": upstream_ok,
        "upstream_error": upstream_error,
        "hermes_agent": "hermes-agent==0.19.0",
    }


@app.get("/v1/models")
async def models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_auth(authorization)
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "hermes-agent",
            }
        ],
    }


async def _proxy_chat(body: dict[str, Any]) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {UPSTREAM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = dict(body)
    payload.setdefault("model", MODEL)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        return await client.post(
            f"{UPSTREAM_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    _require_auth(authorization)
    body = await request.json()
    stream = bool(body.get("stream"))
    logger.info(
        "chat.completions model=%s stream=%s msgs=%s",
        body.get("model", MODEL),
        stream,
        len(body.get("messages") or []),
    )
    try:
        upstream = await _proxy_chat(body)
    except httpx.TimeoutException as exc:
        logger.error("upstream timeout: %s", exc)
        raise HTTPException(status_code=504, detail="Upstream model timeout") from exc
    except httpx.HTTPError as exc:
        logger.error("upstream error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream error: {exc}") from exc

    if stream:
        if upstream.status_code >= 400:
            raise HTTPException(status_code=upstream.status_code, detail=upstream.text)

        async def event_stream():
            async for chunk in upstream.aiter_bytes():
                yield chunk

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    if upstream.status_code == 401:
        raise HTTPException(status_code=502, detail="Upstream rejected API key")
    if upstream.status_code == 429:
        raise HTTPException(status_code=429, detail="Upstream rate limited")
    if upstream.status_code >= 500:
        raise HTTPException(status_code=502, detail=upstream.text[:500])
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.text[:500])

    data = upstream.json()
    # Normalize missing fields for strict clients
    data.setdefault("id", f"chatcmpl-{uuid.uuid4().hex[:20]}")
    data.setdefault("object", "chat.completion")
    data.setdefault("created", int(time.time()))
    data.setdefault("model", body.get("model") or MODEL)
    return JSONResponse(data)


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(ROOT / "logs" / "hermes_gateway.log", encoding="utf-8"),
        ],
    )
    if not API_KEY:
        raise SystemExit("HERMES_API_KEY must be set in .env")
    (ROOT / "logs").mkdir(exist_ok=True)
    logger.info(
        "Hermes gateway listening on %s:%s model=%s upstream=%s",
        HOST,
        PORT,
        MODEL,
        UPSTREAM_BASE_URL,
    )
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Local OpenAI-compatible upstream model server (free / offline fallback).

Used as Hermes Agent's model.base_url when Ollama / cloud providers are
unavailable. Implements /health, /v1/models, /v1/chat/completions.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("local_upstream")

MODEL_ID = os.getenv("LOCAL_MODEL_ID", "hermes-local-mock")
UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY", "local-upstream-key")

app = FastAPI(title="Hermes Local Upstream", version="1.0.0")


def _auth(authorization: str | None) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token.strip() != UPSTREAM_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _assistant_reply(messages: list[dict[str, Any]]) -> str:
    """Deterministic free-model reply for integration / CI without GPU or paid APIs."""
    user_bits: list[str] = []
    system_bits: list[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        text = str(content or "").strip()
        if role == "system" and text:
            system_bits.append(text)
        elif role == "user" and text:
            user_bits.append(text)
        elif role == "tool" and text:
            user_bits.append(f"[tool] {text}")

    last_user = user_bits[-1] if user_bits else ""
    persona = (
        "Я — MarvinDeepSeekBot через Hermes (локальный upstream). "
        "Помогаю с ИИ-агентами, ИИ-сервисами и контент-фабриками."
    )
    if not last_user:
        return f"{persona}\nЗадайте вопрос — отвечу по существу."

    lower = last_user.lower()
    if any(w in lower for w in ("ping", "health", "тест", "test", "привет", "hello")):
        return (
            f"{persona}\n\n"
            f"Статус: OK. Upstream-модель `{MODEL_ID}` отвечает. "
            f"Ваше сообщение: «{last_user[:200]}»."
        )

    tips = (
        "Рекомендации (open-source first): CrewAI / LangGraph для агентов, "
        "Ollama / vLLM для локального инференса, n8n для автоматизации, "
        "crawl4ai + WordPress REST для контент-фабрики."
    )
    sys_note = ""
    if system_bits:
        sys_note = f"\n(учтён system prompt, {len(system_bits)} блок(ов))"
    return (
        f"{persona}{sys_note}\n\n"
        f"Запрос: {last_user[:1500]}\n\n"
        f"Краткий ответ: обработал запрос через локальный OpenAI-совместимый "
        f"upstream `{MODEL_ID}` (бесплатный offline fallback для Hermes). "
        f"{tips}"
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "local_upstream", "model": MODEL_ID}


@app.get("/v1/models")
async def list_models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "hermes-integration",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    _auth(authorization)
    body = await request.json()
    messages = body.get("messages") or []
    model = body.get("model") or MODEL_ID
    # Ignore tool schemas: always return a final assistant message so Hermes
    # agent turn ends quickly in offline/demo mode.
    content = _assistant_reply(messages)
    max_tokens = int(body.get("max_tokens") or 2048)
    content = content[: max(256, max_tokens * 4)]

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    prompt_tokens = sum(len(str(m.get("content", ""))) // 4 for m in messages) or 1
    completion_tokens = max(1, len(content) // 4)

    payload = {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    logger.info("chat.completions model=%s chars=%s", model, len(content))
    return JSONResponse(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local OpenAI-compatible upstream")
    parser.add_argument("--host", default=os.getenv("UPSTREAM_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("UPSTREAM_PORT", "8001")))
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "info"))
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Starting local upstream on %s:%s model=%s", args.host, args.port, MODEL_ID)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())


if __name__ == "__main__":
    main()

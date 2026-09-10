#!/usr/bin/env python3
"""
MarvinDeepSeekBot → Hermes OpenAI-compatible client.

Reads HERMES_API_KEY / HERMES_BASE_URL from .env, sends chat completions to
Hermes (/v1/chat/completions), retries on timeouts / 401 / 429 / 5xx with
exponential backoff, and logs to bot_client.log.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

LOG_FILE = ROOT / "bot_client.log"
CONFIG_PATH = ROOT / "bot_config.yaml"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("marvin_hermes_client")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


logger = setup_logging()


def load_bot_config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise RuntimeError("bot_config.yaml must be a mapping")
    return data


class HermesBotClient:
    """OpenAI-compatible client for Hermes with retries."""

    RETRYABLE_STATUS = {401, 429, 500, 502, 503, 504}

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.config = config or load_bot_config()
        self.base_url = (base_url or os.getenv("HERMES_BASE_URL") or "http://127.0.0.1:8000").rstrip(
            "/"
        )
        self.api_key = api_key or os.getenv("HERMES_API_KEY") or ""
        if not self.api_key:
            raise ValueError("HERMES_API_KEY is required (set in .env)")
        self.timeout = float(self.config.get("timeout_seconds") or 60)
        self.max_retries = int(self.config.get("max_retries") or 4)
        self.model = str(self.config.get("model") or os.getenv("HERMES_MODEL") or "hermes-local-mock")
        self.max_tokens = int(self.config.get("max_tokens") or 2048)
        self.temperature = float(self.config.get("temperature") or 0.7)
        self.system_prompt = str(self.config.get("system_prompt") or "").strip()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(self, user_message: str, *, model: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }
        url = f"{self.base_url}/v1/chat/completions"
        logger.info("REQUEST url=%s model=%s user_chars=%s", url, payload["model"], len(user_message))

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            delay = min(2 ** (attempt - 1), 16)
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, headers=self._headers(), json=payload)
                status = response.status_code
                if status == 200:
                    data = response.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    if not content:
                        raise RuntimeError(f"Empty assistant content: {data!r}")
                    logger.info(
                        "RESPONSE status=200 chars=%s preview=%r",
                        len(content),
                        content[:160],
                    )
                    return str(content)

                body_preview = response.text[:400]
                logger.warning(
                    "RESPONSE status=%s attempt=%s/%s body=%r",
                    status,
                    attempt,
                    self.max_retries,
                    body_preview,
                )
                if status not in self.RETRYABLE_STATUS:
                    raise RuntimeError(f"Hermes error {status}: {body_preview}")
                last_error = RuntimeError(f"Hermes error {status}: {body_preview}")
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("TIMEOUT attempt=%s/%s: %s", attempt, self.max_retries, exc)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("HTTP_ERROR attempt=%s/%s: %s", attempt, self.max_retries, exc)

            if attempt < self.max_retries:
                logger.info("retry sleep=%ss", delay)
                time.sleep(delay)

        assert last_error is not None
        logger.error("FAILED after %s attempts: %s", self.max_retries, last_error)
        raise last_error

    def health(self) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{self.base_url}/health")
            r.raise_for_status()
            return r.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="MarvinDeepSeekBot Hermes client")
    parser.add_argument(
        "message",
        nargs="?",
        default="Привет! Кратко представься и подтверди, что Hermes отвечает.",
        help="User message to send",
    )
    parser.add_argument("--model", default=None, help="Override model id")
    args = parser.parse_args()

    client = HermesBotClient()
    try:
        health = client.health()
        logger.info("health=%s", health)
    except Exception as exc:  # noqa: BLE001
        logger.warning("health check failed: %s", exc)

    reply = client.chat(args.message, model=args.model)
    print(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Integration test: one chat request through Hermes must return assistant text."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bot_client import HermesBotClient  # noqa: E402


def test_bot_client_receives_response() -> None:
    assert os.getenv("HERMES_API_KEY"), "HERMES_API_KEY must be set (load .env before pytest)"
    client = HermesBotClient()
    health = client.health()
    assert health.get("status") in {"ok", "degraded"}
    reply = client.chat("ping: интеграционный тест MarvinDeepSeekBot → Hermes")
    assert isinstance(reply, str)
    assert len(reply.strip()) > 0
    assert "Hermes" in reply or "hermes" in reply.lower() or "Marvin" in reply or "OK" in reply


if __name__ == "__main__":
    # Allow `python test_bot_client.py` without pytest
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    test_bot_client_receives_response()
    print("PASS: test_bot_client_receives_response")

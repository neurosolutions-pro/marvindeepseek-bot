#!/usr/bin/env python3
"""Smoke tests for digest/cursor_prompt prompt builders (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from services.cursor_prompt_service import PROMPT_MODES, build_cursor_prompt_request
from services.digest_service import DIGEST_FORMATS, build_digest_prompt


def test_digest_prompt_contains_sections() -> None:
    text = build_digest_prompt("LangGraph vs CrewAI", "markdown")
    assert "TL;DR" in text
    assert "Источники" in text
    assert "LangGraph vs CrewAI" in text
    assert "markdown" in DIGEST_FORMATS


def test_digest_json_schema_hint() -> None:
    text = build_digest_prompt("тема", "json")
    assert '"tldr"' in text
    assert '"sources"' in text


def test_cursor_prompt_modes() -> None:
    single = build_cursor_prompt_request("добавь /status", "single")
    iterative = build_cursor_prompt_request("добавь /status", "iterative")
    assert "один большой" in single
    assert "итератив" in iterative
    assert set(PROMPT_MODES) == {"single", "iterative"}


if __name__ == "__main__":
    test_digest_prompt_contains_sections()
    test_digest_json_schema_hint()
    test_cursor_prompt_modes()
    print("PASS: digest/cursor_prompt builders")

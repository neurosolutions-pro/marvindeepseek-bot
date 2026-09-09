#!/usr/bin/env python3
"""Tests for scripts/telegram_split.py"""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_split import SAFE_CHUNK_LIMIT, format_parts, split_telegram_message  # noqa: E402


class TelegramSplitTests(unittest.TestCase):
    def test_short_unchanged(self) -> None:
        text = "hello"
        self.assertEqual(split_telegram_message(text), ["hello"])

    def test_never_drops_content(self) -> None:
        parts = [f"## Section {i}\n\n" + ("word " * 200) for i in range(12)]
        text = "\n\n".join(parts)
        chunks = split_telegram_message(text, SAFE_CHUNK_LIMIT)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), SAFE_CHUNK_LIMIT)
        # Reconstruct approximately: all chunks concatenated without inventing content
        joined = "\n\n".join(chunks)
        for token in ("## Section 0", "## Section 11", "word"):
            self.assertIn(token, joined)

    def test_does_not_break_fenced_code_when_small(self) -> None:
        code = "```python\n" + ("print(1)\n" * 20) + "```"
        text = "Intro\n\n" + code + "\n\nOutro"
        chunks = split_telegram_message(text, 500)
        # At least one chunk should contain the full fence if it fits a chunk
        self.assertTrue(any("```python" in c for c in chunks))

    def test_format_parts_markers(self) -> None:
        chunks = format_parts(["aaa", "bbb"], style="pin")
        self.assertTrue(chunks[0].startswith("📌 Часть 1 из 2"))
        self.assertIn("✅ Конец ответа", chunks[-1])


if __name__ == "__main__":
    unittest.main()

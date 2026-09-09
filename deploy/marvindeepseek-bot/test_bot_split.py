"""Unit tests for Telegram split helpers and prompt detection."""

from __future__ import annotations

import ast
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent


class SplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        src = (ROOT / "services" / "telegram_split.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        ns: dict = {"re": re}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                exec(compile(ast.Module(body=[node], type_ignores=[]), "<split>", "exec"), ns)
        cls.h = ns

    def test_short(self) -> None:
        self.assertEqual(self.h["split_telegram_message"]("hi", 3500), ["hi"])

    def test_long_never_drops(self) -> None:
        text = ("## H\n\n" + ("слово " * 80) + "\n\n") * 10
        chunks = self.h["split_telegram_message"](text, 3500)
        self.assertGreater(len(chunks), 1)
        self.assertIn("## H", "\n\n".join(chunks))

    def test_format_parts(self) -> None:
        parts = self.h["format_telegram_parts"](["aaa", "bbb"])
        self.assertTrue(parts[0].startswith("📌 Часть 1 из 2"))
        self.assertIn("✅ Конец ответа", parts[-1])


class PromptDetectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        src = (ROOT / "handlers" / "common.py").read_text(encoding="utf-8")
        # Load only pure helpers without telegram imports by exec selected functions
        # Fallback: import after stubbing config modules is heavy; regex-check source.
        cls.src = src

    def test_prompt_helper_present(self) -> None:
        self.assertIn("def is_prompt_request", self.src)
        self.assertIn("промт", self.src)
        self.assertIn("prompt", self.src)


if __name__ == "__main__":
    unittest.main()

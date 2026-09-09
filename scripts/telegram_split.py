#!/usr/bin/env python3
"""Deterministic Telegram message splitter for MarvinDeepSeekBot.

Prefer natural Markdown boundaries. Never truncate the overall answer —
always return chunks that together reconstruct the full text (modulo
boundary whitespace joins).
"""

from __future__ import annotations

import argparse
import re
from typing import List

TELEGRAM_HARD_LIMIT = 4096
SAFE_CHUNK_LIMIT = 3500


def _hard_split(text: str, max_len: int) -> List[str]:
    return [text[i : i + max_len] for i in range(0, len(text), max_len)] or [""]


def _split_block(block: str, max_len: int) -> List[str]:
    if len(block) <= max_len:
        return [block]

    paragraphs = re.split(r"\n\n+", block)
    if len(paragraphs) > 1:
        out: List[str] = []
        current = ""
        for para in paragraphs:
            candidate = para if current == "" else f"{current}\n\n{para}"
            if len(candidate) <= max_len:
                current = candidate
            else:
                if current:
                    out.extend(_split_block(current, max_len))
                current = para
        if current:
            out.extend(_split_block(current, max_len))
        return out

    lines = block.split("\n")
    if len(lines) > 1:
        out = []
        current = ""
        for line in lines:
            candidate = line if current == "" else f"{current}\n{line}"
            if len(candidate) <= max_len:
                current = candidate
            else:
                if current:
                    out.extend(_split_block(current, max_len))
                current = line
        if current:
            out.extend(_split_block(current, max_len))
        return out

    return _hard_split(block, max_len)


def split_telegram_message(text: str, max_len: int = SAFE_CHUNK_LIMIT) -> List[str]:
    """Split text into chunks each <= max_len characters."""
    if max_len < 64:
        raise ValueError("max_len must be >= 64")
    if len(text) <= max_len:
        return [text]
    return _split_block(text, max_len)


def format_parts(chunks: List[str], style: str = "pin") -> List[str]:
    """Add part markers. style: 'pin' (📌) or 'paren' ((1/N))."""
    n = len(chunks)
    if n <= 1:
        return list(chunks)
    out: List[str] = []
    for i, chunk in enumerate(chunks, start=1):
        if style == "paren":
            header = f"({i}/{n})\n"
        else:
            header = f"📌 Часть {i} из {n}\n"
        body = chunk
        if i == n and style == "pin":
            body = f"{chunk.rstrip()}\n\n✅ Конец ответа"
        out.append(f"{header}{body}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="File to split (default: stdin)")
    parser.add_argument("--max", type=int, default=SAFE_CHUNK_LIMIT)
    parser.add_argument("--format", choices=("pin", "paren", "raw"), default="raw")
    args = parser.parse_args()
    text = open(args.path, encoding="utf-8").read() if args.path else __import__("sys").stdin.read()
    chunks = split_telegram_message(text, args.max)
    if args.format != "raw":
        chunks = format_parts(chunks, style=args.format)
    for i, chunk in enumerate(chunks, 1):
        print(f"===== CHUNK {i}/{len(chunks)} ({len(chunk)} chars) =====")
        print(chunk)


if __name__ == "__main__":
    main()

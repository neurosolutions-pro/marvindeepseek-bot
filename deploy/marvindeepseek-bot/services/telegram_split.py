"""Telegram message splitting helpers."""

from __future__ import annotations

import re


def hard_split(text: str, max_len: int) -> list[str]:
    return [text[i : i + max_len] for i in range(0, len(text), max_len)] or [""]


def split_block(block: str, max_len: int) -> list[str]:
    if len(block) <= max_len:
        return [block]

    paragraphs = re.split(r"\n\n+", block)
    if len(paragraphs) > 1:
        out: list[str] = []
        current = ""
        for para in paragraphs:
            candidate = para if current == "" else f"{current}\n\n{para}"
            if len(candidate) <= max_len:
                current = candidate
            else:
                if current:
                    out.extend(split_block(current, max_len))
                current = para
        if current:
            out.extend(split_block(current, max_len))
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
                    out.extend(split_block(current, max_len))
                current = line
        if current:
            out.extend(split_block(current, max_len))
        return out

    return hard_split(block, max_len)


def split_telegram_message(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    return split_block(text, max_len)


def format_telegram_parts(chunks: list[str]) -> list[str]:
    n = len(chunks)
    if n <= 1:
        return list(chunks)
    out: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        body = chunk
        if i == n:
            body = f"{chunk.rstrip()}\n\n✅ Конец ответа"
        header = f"📌 Часть {i} из {n}\n"
        out.append(f"{header}{body}")
    return out

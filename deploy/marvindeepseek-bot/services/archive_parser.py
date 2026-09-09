"""ZIP archive extraction helpers."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

log = logging.getLogger("marvindeepseek.archive")

MAX_MEMBERS = 30
MAX_MEMBER_SIZE = 5 * 1024 * 1024


def parse_zip(file_path: str) -> str:
    """Extract and summarize text-like members from a ZIP archive."""
    path = Path(file_path)
    if not zipfile.is_zipfile(path):
        return "Файл не является корректным ZIP-архивом."

    parts: list[str] = []
    with zipfile.ZipFile(path, "r") as zf:
        members = [i for i in zf.infolist() if not i.is_dir()]
        if len(members) > MAX_MEMBERS:
            return f"В архиве слишком много файлов ({len(members)}). Лимит: {MAX_MEMBERS}."
        for info in members[:MAX_MEMBERS]:
            name = info.filename
            if ".." in name or name.startswith("/") or name.startswith("\\"):
                parts.append(f"[пропущен небезопасный путь: {name}]")
                continue
            if info.file_size > MAX_MEMBER_SIZE:
                parts.append(f"[пропущен большой файл: {name}, {info.file_size} байт]")
                continue
            ext = Path(name).suffix.lower()
            try:
                data = zf.read(info)
            except Exception as exc:
                log.exception("zip read failed: %s", name)
                parts.append(f"[ошибка чтения {name}: {exc}]")
                continue
            if ext in {".txt", ".md", ".csv", ".json", ".py", ".log"}:
                text = data.decode("utf-8", errors="replace")
                parts.append(f"=== {name} ===\n{text[:8000]}")
            else:
                parts.append(f"=== {name} ===\n(бинарный/нетекстовый файл, {info.file_size} байт)")
    return "\n\n".join(parts) if parts else "(Архив пуст)"

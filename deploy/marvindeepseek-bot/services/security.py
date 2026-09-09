"""Basic file security checks (size, extension, magic bytes; optional clamav)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from config import MAX_FILE_SIZE, SUPPORTED_EXTENSIONS

log = logging.getLogger("marvindeepseek.security")

MAGIC_PREFIXES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),
    ".zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".docx": (b"PK\x03\x04",),
    ".xlsx": (b"PK\x03\x04",),
}


class FileSecurityError(Exception):
    """Raised when a file fails security checks."""


def check_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise FileSecurityError(f"Неподдерживаемый формат: {ext or '(без расширения)'}")
    return ext


def check_size(size: int | None) -> None:
    if size is None:
        return
    if size <= 0:
        raise FileSecurityError("Пустой файл.")
    if size > MAX_FILE_SIZE:
        mb = MAX_FILE_SIZE // (1024 * 1024)
        raise FileSecurityError(f"Файл слишком большой. Лимит: {mb} МБ.")


def check_magic(path: Path, ext: str) -> None:
    prefixes = MAGIC_PREFIXES.get(ext)
    if not prefixes:
        return
    head = path.read_bytes()[:16]
    if not any(head.startswith(p) for p in prefixes):
        # webp also needs WEBP at offset 8
        if ext == ".webp" and head.startswith(b"RIFF") and b"WEBP" in head:
            return
        raise FileSecurityError(
            f"Содержимое файла не соответствует расширению {ext}."
        )


def scan_clamav(path: Path) -> None:
    clam = shutil.which("clamscan")
    if not clam:
        return
    try:
        proc = subprocess.run(
            [clam, "--no-summary", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception as exc:
        log.warning("clamav scan skipped: %s", exc)
        return
    if proc.returncode == 1:
        raise FileSecurityError("Файл отклонён антивирусом.")
    if proc.returncode not in (0, 1):
        log.warning("clamav unexpected code=%s out=%s", proc.returncode, proc.stdout[:200])


def validate_saved_file(path: Path, filename: str, size: int | None = None) -> str:
    ext = check_extension(filename)
    check_size(size if size is not None else path.stat().st_size)
    check_magic(path, ext)
    scan_clamav(path)
    return ext

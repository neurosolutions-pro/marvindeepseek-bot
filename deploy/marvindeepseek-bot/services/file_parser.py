"""Extract text from uploaded documents/images."""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("marvindeepseek.file_parser")


def parse_file(file_path: str, file_name: str) -> str:
    """Извлекает текст из файла в зависимости от его типа."""
    ext = os.path.splitext(file_name)[1].lower()
    try:
        if ext == ".pdf":
            return _parse_pdf(file_path)
        if ext in {".docx", ".doc"}:
            return _parse_word(file_path)
        if ext in {".xlsx", ".xls", ".csv"}:
            return _parse_excel(file_path)
        if ext in {".png", ".jpg", ".jpeg", ".webp"}:
            return _parse_image(file_path)
        if ext in {".txt", ".md"}:
            return _parse_text(file_path)
        if ext == ".zip":
            from services.archive_parser import parse_zip

            return parse_zip(file_path)
        return f"Неподдерживаемый формат файла: {ext}"
    except Exception as exc:
        log.exception("parse_file failed for %s", file_name)
        return f"Ошибка чтения файла {file_name}: {exc}"


def _parse_pdf(file_path: str) -> str:
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    text = "\n".join(text_parts).strip()
    return text or "(PDF без извлекаемого текста)"


def _parse_word(file_path: str) -> str:
    from docx import Document

    doc = Document(file_path)
    text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    return text or "(Word-документ пуст)"


def _parse_excel(file_path: str) -> str:
    import pandas as pd

    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(file_path)
        return df.to_string()
    sheets = pd.read_excel(file_path, sheet_name=None)
    chunks: list[str] = []
    for sheet_name, df in sheets.items():
        chunks.append(f"\n--- Лист: {sheet_name} ---\n{df.to_string()}")
    return "\n".join(chunks).strip() or "(Excel пуст)"


def _parse_image(file_path: str) -> str:
    import pytesseract
    from PIL import Image

    img = Image.open(file_path)
    text = pytesseract.image_to_string(img, lang="rus+eng").strip()
    return text or "(На изображении не распознан текст)"


def _parse_text(file_path: str) -> str:
    raw = Path(file_path).read_bytes()
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")

"""Word document generation."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt

from config import DOWNLOADS_DIR


def generate_word(text: str, filename: str = "output.docx") -> str:
    """Генерирует Word-документ. Возвращает путь к файлу."""
    out = Path(filename)
    if not out.is_absolute():
        out = DOWNLOADS_DIR / out.name

    doc = Document()
    for line in text.split("\n"):
        p = doc.add_paragraph(line)
        for run in p.runs:
            run.font.size = Pt(12)
    doc.save(str(out))
    return str(out)

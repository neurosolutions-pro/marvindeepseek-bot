"""PDF generation with Cyrillic-capable fonts."""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from config import DEJAVU_CANDIDATES, DOWNLOADS_DIR

log = logging.getLogger("marvindeepseek.pdf")

_FONT_NAME: str | None = None


def _resolve_font() -> str:
    global _FONT_NAME
    if _FONT_NAME:
        return _FONT_NAME
    for candidate in DEJAVU_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont("DejaVuSans", str(path)))
                _FONT_NAME = "DejaVuSans"
                return _FONT_NAME
            except Exception:
                log.exception("font register failed: %s", path)
    _FONT_NAME = "Helvetica"
    log.warning("DejaVuSans not found; PDF may not render Cyrillic correctly")
    return _FONT_NAME


def generate_pdf(text: str, filename: str = "output.pdf") -> str:
    """Генерирует PDF с русским текстом. Возвращает путь к файлу."""
    out = Path(filename)
    if not out.is_absolute():
        out = DOWNLOADS_DIR / out.name

    font_name = _resolve_font()
    c = canvas.Canvas(str(out), pagesize=A4)
    width, height = A4
    y = height - 50
    margin = 50
    text_width = width - 2 * margin
    lines = simpleSplit(text.replace("\t", "    "), font_name, 12, text_width)

    for line in lines:
        if y < 50:
            c.showPage()
            y = height - 50
        c.setFont(font_name, 12)
        c.drawString(margin, y, line)
        y -= 16

    c.save()
    return str(out)

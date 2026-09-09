"""Excel workbook generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook

from config import DOWNLOADS_DIR


def generate_excel(data: dict[str, list[list[Any]]], filename: str = "output.xlsx") -> str:
    """
    Генерирует Excel-файл.

    data — словарь {название_листа: список строк (каждая строка — список ячеек)}.
    """
    out = Path(filename)
    if not out.is_absolute():
        out = DOWNLOADS_DIR / out.name

    wb = Workbook()
    # remove default sheet if we create named ones
    default = wb.active
    first = True
    for sheet_name, rows in data.items():
        safe_name = (sheet_name or "Лист1")[:31]
        if first:
            ws = default
            ws.title = safe_name
            first = False
        else:
            ws = wb.create_sheet(title=safe_name)
        for row in rows:
            ws.append(list(row))
    if first:
        default.title = "Результат"
        default.append(["Пусто"])
    wb.save(str(out))
    return str(out)

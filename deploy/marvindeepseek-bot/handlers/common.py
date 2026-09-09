"""Shared helpers for Telegram handlers."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import (
    ALLOWED_USERS,
    ADMIN_CHAT_IDS,
    DOWNLOADS_DIR,
    MAX_FILES_PER_DAY,
    MAX_HISTORY,
    TELEGRAM_CHUNK_LIMIT,
)
from services.telegram_split import format_telegram_parts, hard_split, split_telegram_message

log = logging.getLogger("marvindeepseek")

history: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))


def allowed(user_id: int | None) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id is not None and user_id in ALLOWED_USERS


def is_prompt_request(text: str) -> bool:
    t = text.lower()
    if any(k in t for k in ("промт", "промпт", "prompt")):
        return True
    if "шаблон" in t and any(
        k in t for k in ("промт", "промпт", "prompt", "llm", "gpt", "нейросет", "deepseek")
    ):
        return True
    if "запрос" in t and any(
        k in t for k in ("llm", "gpt", "chatgpt", "deepseek", "нейросет", "ии-модел", "промт", "промпт")
    ):
        return True
    return False


def wants_excel(text: str) -> bool:
    t = text.lower()
    keys = (
        "excel",
        "xlsx",
        "таблиц",
        "сделай таблицу",
        "составь таблицу",
        "отчёт в excel",
        "отчет в excel",
        "выгрузка в excel",
    )
    return any(k in t for k in keys)


def wants_word(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ("word", "docx", "документ word", "файл word"))


def wants_pdf(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ("pdf", "в pdf", "файлом pdf"))


def file_quota_ok(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    today = date.today().isoformat()
    bucket = context.user_data.setdefault("file_quota", {"day": today, "count": 0})
    if bucket.get("day") != today:
        bucket["day"] = today
        bucket["count"] = 0
    return int(bucket.get("count", 0)) < MAX_FILES_PER_DAY


def bump_file_quota(context: ContextTypes.DEFAULT_TYPE) -> None:
    today = date.today().isoformat()
    bucket = context.user_data.setdefault("file_quota", {"day": today, "count": 0})
    if bucket.get("day") != today:
        bucket["day"] = today
        bucket["count"] = 0
    bucket["count"] = int(bucket.get("count", 0)) + 1


async def reply_long(update: Update, text: str) -> None:
    header_budget = 40
    chunk_limit = max(512, min(TELEGRAM_CHUNK_LIMIT, 4096 - header_budget))
    parts = format_telegram_parts(split_telegram_message(text, chunk_limit))
    for part in parts:
        chunks = [part] if len(part) <= 4096 else hard_split(part, 4096)
        for sub in chunks:
            try:
                await update.message.reply_text(sub, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await update.message.reply_text(sub)


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if not ADMIN_CHAT_IDS:
        return
    for chat_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text[:3500])
        except Exception:
            log.exception("admin notify failed for %s", chat_id)


def cleanup_path(path: str | Path | None) -> None:
    if not path:
        return
    p = Path(path)
    try:
        if p.exists() and p.is_file():
            # only delete inside downloads/
            if DOWNLOADS_DIR.resolve() in p.resolve().parents or p.parent.resolve() == DOWNLOADS_DIR.resolve():
                p.unlink(missing_ok=True)
    except Exception:
        log.exception("cleanup failed: %s", path)

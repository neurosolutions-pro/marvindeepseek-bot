"""Command handlers."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from handlers.common import allowed, history, reply_long
from services import memory_service

log = logging.getLogger("marvindeepseek.commands")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not allowed(user.id if user else None):
        await update.message.reply_text("Доступ ограничен.")
        return
    history[update.effective_chat.id].clear()
    if user:
        await memory_service.ensure_user_entity(user.id, user.full_name)
    mem = "включена" if memory_service.memory_client() else "выключена"
    await update.message.reply_text(
        "Привет! Я MarvinDeepSeekBot.\n"
        "Я умею:\n"
        "📄 принимать файлы (PDF, Word, Excel, изображения, txt, zip)\n"
        "🎤 распознавать голосовые сообщения\n"
        "📝 отвечать на текстовые запросы\n"
        "📊 генерировать PDF / Word / Excel\n"
        f"🧠 память: {mem}\n\n"
        "Отправьте файл или напишите сообщение.\n"
        "Команды: /help /file /clear /memory /remember"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update.effective_user.id if update.effective_user else None):
        return
    await update.message.reply_text(
        "Команды:\n"
        "/start — приветствие\n"
        "/help — эта справка\n"
        "/file — какие файлы можно присылать\n"
        "/clear — очистить историю диалога\n"
        "/memory — показать долговременную память\n"
        "/remember <факт> — сохранить факт в память\n\n"
        "Также:\n"
        "• запросы с «промт/prompt» → выбор формата (текст/PDF)\n"
        "• «сделай таблицу/excel» → файл .xlsx\n"
        "• голосовые сообщения → распознавание и ответ"
    )


async def cmd_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update.effective_user.id if update.effective_user else None):
        return
    await update.message.reply_text(
        "Можно отправлять:\n"
        "• PDF (.pdf)\n"
        "• Word (.doc, .docx)\n"
        "• Excel (.xls, .xlsx, .csv)\n"
        "• изображения (.png, .jpg, .jpeg, .webp) — OCR\n"
        "• текст (.txt, .md)\n"
        "• ZIP-архивы (.zip)\n"
        "• голосовые сообщения Telegram\n\n"
        "Лимит размера: 20 МБ.\n"
        "Подпись к файлу = ваш вопрос (если пусто: «Проанализируй этот файл»)."
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update.effective_user.id if update.effective_user else None):
        return
    history[update.effective_chat.id].clear()
    await update.message.reply_text(
        "История диалога очищена (долговременная память сохранена)."
    )


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not allowed(user.id if user else None):
        return
    client = memory_service.memory_client()
    if not client:
        await update.message.reply_text("Память отключена.")
        return
    try:
        ok = await client.health()
        data = await client.open_nodes([memory_service.user_entity(user.id)])
        block = memory_service.format_memory_block(data) or "(пока пусто)"
        await reply_long(
            update,
            f"Статус memory-mcp: {'ok' if ok else 'down'}\n\nВаша память:\n{block}",
        )
    except Exception as exc:
        log.exception("cmd_memory failed")
        await update.message.reply_text(f"Не удалось прочитать память: {exc}")


async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not allowed(user.id if user else None):
        return
    fact = " ".join(context.args).strip() if context.args else ""
    if not fact and update.message and update.message.text:
        parts = update.message.text.split(maxsplit=1)
        fact = parts[1].strip() if len(parts) > 1 else ""
    try:
        msg = await memory_service.remember_fact(user.id, fact)
        await update.message.reply_text(msg)
    except Exception as exc:
        log.exception("cmd_remember failed")
        await update.message.reply_text(f"Не удалось сохранить: {exc}")

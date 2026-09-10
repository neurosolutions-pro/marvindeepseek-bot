"""Command handlers."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from handlers.common import allowed, history, reply_long
from services import memory_service
from services.cursor_prompt_service import generate_cursor_prompt
from services.digest_service import DIGEST_FORMATS, generate_digest
from services.status_service import build_status_report

log = logging.getLogger("marvindeepseek.commands")


def _digest_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Короткий", callback_data="digest_fmt:short"),
                InlineKeyboardButton("Отчёт", callback_data="digest_fmt:report"),
                InlineKeyboardButton("Таблица", callback_data="digest_fmt:table"),
            ],
            [
                InlineKeyboardButton("Markdown", callback_data="digest_fmt:markdown"),
                InlineKeyboardButton("JSON", callback_data="digest_fmt:json"),
            ],
        ]
    )


def _cursor_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Один большой промт", callback_data="cursor_mode:single"
                ),
                InlineKeyboardButton(
                    "Серия итераций", callback_data="cursor_mode:iterative"
                ),
            ]
        ]
    )


def _command_arg_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    text = " ".join(context.args).strip() if context.args else ""
    if text:
        return text
    if update.message and update.message.text:
        parts = update.message.text.split(maxsplit=1)
        if len(parts) > 1:
            return parts[1].strip()
    return ""


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
        "🧾 собирать сводки (/digest)\n"
        "🛠 генерировать промты для Cursor (/cursor_prompt)\n"
        f"🧠 память: {mem}\n\n"
        "Отправьте файл или напишите сообщение.\n"
        "Команды: /help /status /digest /cursor_prompt /file /clear /memory /remember"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update.effective_user.id if update.effective_user else None):
        return
    await update.message.reply_text(
        "Команды:\n"
        "/start — приветствие\n"
        "/help — эта справка\n"
        "/status — активная LLM и подключения (Hermes, MCP)\n"
        "/digest <тема> — сводка/дайджест (выбор формата)\n"
        "/cursor_prompt <задача> — промт для Cursor (один / серия)\n"
        "/file — какие файлы можно присылать\n"
        "/clear — очистить историю диалога\n"
        "/memory — показать долговременную память\n"
        "/remember <факт> — сохранить факт в память\n\n"
        "Также:\n"
        "• запросы с «промт/prompt» → выбор формата (текст/PDF)\n"
        "• «сделай таблицу/excel» → файл .xlsx\n"
        "• голосовые сообщения → распознавание и ответ"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show active LLM provider and connected MCP/backends (incl. Hermes)."""
    if not allowed(update.effective_user.id if update.effective_user else None):
        await update.message.reply_text("Доступ ограничен.")
        return
    try:
        report = await build_status_report()
        await reply_long(update, report)
    except Exception as exc:
        log.exception("cmd_status failed")
        await update.message.reply_text(f"Не удалось собрать статус: {exc}")


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start digest flow: topic -> format buttons -> generated summary."""
    if not allowed(update.effective_user.id if update.effective_user else None):
        await update.message.reply_text("Доступ ограничен.")
        return
    topic = _command_arg_text(update, context)
    if not topic:
        context.user_data["awaiting_digest_topic"] = True
        await update.message.reply_text(
            "Пришлите тему для сводки одним сообщением.\n"
            "Пример: /digest Сравнение SearxNG и DuckDuckGo для AI-агентов"
        )
        return
    context.user_data["pending_digest_topic"] = topic
    context.user_data["awaiting_digest_topic"] = False
    formats = ", ".join(DIGEST_FORMATS.keys())
    await update.message.reply_text(
        f"Тема: {topic}\nВыберите формат сводки ({formats}):",
        reply_markup=_digest_keyboard(),
    )


async def cmd_cursor_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start Cursor prompt flow: task -> single/iterative -> generated prompt."""
    if not allowed(update.effective_user.id if update.effective_user else None):
        await update.message.reply_text("Доступ ограничен.")
        return
    task = _command_arg_text(update, context)
    if not task:
        context.user_data["awaiting_cursor_task"] = True
        await update.message.reply_text(
            "Пришлите задачу для Cursor-промта одним сообщением.\n"
            "Пример: /cursor_prompt Добавь endpoint /health в FastAPI и тесты"
        )
        return
    context.user_data["pending_cursor_task"] = task
    context.user_data["awaiting_cursor_task"] = False
    await update.message.reply_text(
        f"Задача: {task}\nКак генерировать промт?",
        reply_markup=_cursor_mode_keyboard(),
    )


async def handle_digest_format_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not allowed(update.effective_user.id if update.effective_user else None):
        await query.edit_message_text("Доступ ограничен.")
        return
    topic = context.user_data.get("pending_digest_topic")
    if not topic:
        await query.edit_message_text(
            "Нет темы для сводки. Отправьте /digest <тема>."
        )
        return
    fmt = (query.data or "").split(":", 1)[-1]
    if fmt not in DIGEST_FORMATS:
        await query.edit_message_text("Неизвестный формат.")
        return
    await query.edit_message_text(f"Собираю сводку ({DIGEST_FORMATS[fmt]})…")
    chat_id = query.message.chat_id
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        result = await generate_digest(topic, fmt)
        # reply_long needs Update with message; send manually in chunks via bot
        from config import TELEGRAM_CHUNK_LIMIT
        from services.telegram_split import format_telegram_parts, split_telegram_message

        parts = format_telegram_parts(
            split_telegram_message(result, max(512, min(TELEGRAM_CHUNK_LIMIT, 4050)))
        )
        for part in parts:
            await context.bot.send_message(chat_id=chat_id, text=part)
    except Exception as exc:
        log.exception("digest callback failed")
        await context.bot.send_message(
            chat_id=chat_id, text=f"Не удалось собрать сводку: {exc}"
        )
    finally:
        context.user_data["pending_digest_topic"] = None


async def handle_cursor_mode_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not allowed(update.effective_user.id if update.effective_user else None):
        await query.edit_message_text("Доступ ограничен.")
        return
    task = context.user_data.get("pending_cursor_task")
    if not task:
        await query.edit_message_text(
            "Нет задачи. Отправьте /cursor_prompt <задача>."
        )
        return
    mode = (query.data or "").split(":", 1)[-1]
    if mode not in {"single", "iterative"}:
        await query.edit_message_text("Неизвестный режим.")
        return
    label = "один промт" if mode == "single" else "серия итераций"
    await query.edit_message_text(f"Генерирую Cursor-промт ({label})…")
    chat_id = query.message.chat_id
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        result = await generate_cursor_prompt(task, mode)
        from config import TELEGRAM_CHUNK_LIMIT
        from services.telegram_split import format_telegram_parts, split_telegram_message

        parts = format_telegram_parts(
            split_telegram_message(result, max(512, min(TELEGRAM_CHUNK_LIMIT, 4050)))
        )
        for part in parts:
            await context.bot.send_message(chat_id=chat_id, text=part)
    except Exception as exc:
        log.exception("cursor_prompt callback failed")
        await context.bot.send_message(
            chat_id=chat_id, text=f"Не удалось сгенерировать промт: {exc}"
        )
    finally:
        context.user_data["pending_cursor_task"] = None


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

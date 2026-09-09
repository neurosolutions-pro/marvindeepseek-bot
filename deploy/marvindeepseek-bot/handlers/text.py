"""Text message + prompt format callbacks + excel/pdf/word generation."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from handlers.common import (
    allowed,
    cleanup_path,
    history,
    is_prompt_request,
    notify_admins,
    reply_long,
    wants_excel,
    wants_pdf,
    wants_word,
)
from services import memory_service
from services.excel_generator import generate_excel
from services.llm_service import LLMService
from services.pdf_generator import generate_pdf
from services.word_generator import generate_word

log = logging.getLogger("marvindeepseek.text")
llm = LLMService()


def prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("1️⃣ Текст", callback_data="prompt_fmt:text"),
                InlineKeyboardButton("2️⃣ PDF", callback_data="prompt_fmt:pdf"),
            ]
        ]
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    if not allowed(user.id if user else None):
        await update.message.reply_text("Доступ ограничен.")
        return

    text = update.message.text.strip()
    if not text:
        return

    # If waiting for legacy 1/2 choice, ignore — prefer inline buttons.
    if is_prompt_request(text):
        context.user_data["pending_prompt"] = text
        await update.message.reply_text(
            "Вы хотите получить промт в виде:",
            reply_markup=prompt_keyboard(),
        )
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    hist = history[chat_id]
    hist.append({"role": "user", "content": text})

    memory_block = ""
    if memory_service.memory_client() and user:
        await memory_service.ensure_user_entity(user.id, user.full_name)
        memory_block = await memory_service.load_memory_context(user.id, text)

    try:
        if wants_excel(text):
            rows = await llm.generate_excel_rows(text)
            path = generate_excel({"Отчёт": rows}, filename=f"report_{uuid.uuid4().hex[:8]}.xlsx")
            try:
                with open(path, "rb") as fh:
                    await update.message.reply_document(document=fh, filename=Path(path).name)
            finally:
                cleanup_path(path)
            answer = f"Готово: Excel-файл ({len(rows)} строк)."
        else:
            answer = await llm.generate_response(
                text,
                memory_block=memory_block,
                history=list(hist),
            )
            if wants_word(text):
                path = generate_word(answer, filename=f"answer_{uuid.uuid4().hex[:8]}.docx")
                try:
                    with open(path, "rb") as fh:
                        await update.message.reply_document(document=fh, filename=Path(path).name)
                finally:
                    cleanup_path(path)
            elif wants_pdf(text):
                path = generate_pdf(answer, filename=f"answer_{uuid.uuid4().hex[:8]}.pdf")
                try:
                    with open(path, "rb") as fh:
                        await update.message.reply_document(document=fh, filename=Path(path).name)
                finally:
                    cleanup_path(path)
            else:
                await reply_long(update, answer)
    except Exception as exc:
        log.exception("handle_text failed")
        hist.pop()
        await update.message.reply_text(
            "Не удалось обработать запрос. Попробуйте ещё раз."
        )
        await notify_admins(context, f"critical handle_text: {exc}")
        return

    hist.append({"role": "assistant", "content": answer})
    if memory_service.memory_client() and user:
        await memory_service.remember_turn(user.id, text, answer)


async def handle_prompt_format_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = update.effective_user
    if not allowed(user.id if user else None):
        await query.edit_message_text("Доступ ограничен.")
        return

    pending = context.user_data.get("pending_prompt")
    if not pending:
        await query.edit_message_text("Нет ожидающего запроса промта. Отправьте запрос снова.")
        return

    data = query.data or ""
    fmt = data.split(":", 1)[1] if ":" in data else ""
    await query.edit_message_text("Генерирую промт…")

    try:
        prompt = await llm.generate_response(
            f"Составь качественный готовый промт на основе запроса пользователя.\n"
            f"Верни только текст промта без пояснений.\n\nЗапрос:\n{pending}"
        )
        if fmt == "pdf":
            path = generate_pdf(prompt, filename=f"prompt_{uuid.uuid4().hex[:8]}.pdf")
            try:
                with open(path, "rb") as fh:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=fh,
                        filename=Path(path).name,
                        caption="Ваш промт в PDF",
                    )
            finally:
                cleanup_path(path)
            await context.bot.send_message(chat_id=query.message.chat_id, text="✅ PDF готов.")
        else:
            from config import TELEGRAM_CHUNK_LIMIT
            from services.telegram_split import format_telegram_parts, split_telegram_message

            parts = format_telegram_parts(
                split_telegram_message(prompt, max(512, min(TELEGRAM_CHUNK_LIMIT, 4050)))
            )
            for part in parts:
                await context.bot.send_message(chat_id=query.message.chat_id, text=part)
    except Exception as exc:
        log.exception("prompt callback failed")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"Не удалось сгенерировать промт: {exc}",
        )
        await notify_admins(context, f"critical prompt_callback: {exc}")
    finally:
        context.user_data["pending_prompt"] = None

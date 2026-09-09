"""Document / photo file handlers."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config import DOWNLOADS_DIR, MAX_FILE_SIZE, MAX_FILES_PER_DAY
from handlers.common import (
    allowed,
    bump_file_quota,
    cleanup_path,
    file_quota_ok,
    history,
    notify_admins,
    reply_long,
)
from services import memory_service
from services.file_parser import parse_file
from services.llm_service import LLMService
from services.security import FileSecurityError, validate_saved_file

log = logging.getLogger("marvindeepseek.files")
llm = LLMService()


async def _download_telegram_file(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    file_id: str,
    file_name: str,
    file_size: int | None,
) -> Path:
    tg_file = await context.bot.get_file(file_id)
    safe_name = Path(file_name).name.replace(" ", "_")
    target = DOWNLOADS_DIR / f"{uuid.uuid4().hex[:10]}_{safe_name}"
    await tg_file.download_to_drive(custom_path=str(target))
    validate_saved_file(target, safe_name, size=file_size)
    return target


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.document:
        return
    user = update.effective_user
    if not allowed(user.id if user else None):
        await update.message.reply_text("Доступ ограничен.")
        return
    if not file_quota_ok(context, user.id):
        await update.message.reply_text(
            f"Дневной лимит файлов исчерпан ({MAX_FILES_PER_DAY}/день)."
        )
        return

    doc = update.message.document
    file_name = doc.file_name or "document.bin"
    file_size = doc.file_size
    path: Path | None = None

    try:
        if file_size and file_size > MAX_FILE_SIZE:
            raise FileSecurityError(
                f"Файл слишком большой. Лимит: {MAX_FILE_SIZE // (1024 * 1024)} МБ."
            )
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        path = await _download_telegram_file(
            context,
            file_id=doc.file_id,
            file_name=file_name,
            file_size=file_size,
        )
        bump_file_quota(context)
        extracted = parse_file(str(path), file_name)
        user_message = (update.message.caption or "").strip() or "Проанализируй этот файл"
        prompt = (
            f"{user_message}\n\nИмя файла: {file_name}\n\n"
            f"Содержимое файла:\n{extracted[:60000]}"
        )

        hist = history[update.effective_chat.id]
        hist.append({"role": "user", "content": prompt})
        memory_block = ""
        if memory_service.memory_client() and user:
            await memory_service.ensure_user_entity(user.id, user.full_name)
            memory_block = await memory_service.load_memory_context(user.id, user_message)

        answer = await llm.generate_response(
            prompt, memory_block=memory_block, history=list(hist)
        )
        hist.append({"role": "assistant", "content": answer})
        await reply_long(update, answer)
        if memory_service.memory_client() and user:
            await memory_service.remember_turn(user.id, user_message, answer)
    except FileSecurityError as exc:
        await update.message.reply_text(f"Файл отклонён: {exc}")
    except Exception as exc:
        log.exception("handle_document failed")
        await update.message.reply_text(
            "Не удалось обработать файл. Проверьте формат и попробуйте снова."
        )
        await notify_admins(context, f"critical handle_document: {exc}")
    finally:
        cleanup_path(path)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return
    user = update.effective_user
    if not allowed(user.id if user else None):
        await update.message.reply_text("Доступ ограничен.")
        return
    if not file_quota_ok(context, user.id):
        await update.message.reply_text(
            f"Дневной лимит файлов исчерпан ({MAX_FILES_PER_DAY}/день)."
        )
        return

    photo = update.message.photo[-1]
    path: Path | None = None
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        path = await _download_telegram_file(
            context,
            file_id=photo.file_id,
            file_name="photo.jpg",
            file_size=photo.file_size,
        )
        bump_file_quota(context)
        extracted = parse_file(str(path), "photo.jpg")
        user_message = (update.message.caption or "").strip() or "Распознай текст на изображении и проанализируй"
        prompt = f"{user_message}\n\nOCR:\n{extracted[:60000]}"
        hist = history[update.effective_chat.id]
        hist.append({"role": "user", "content": prompt})
        answer = await llm.generate_response(prompt, history=list(hist))
        hist.append({"role": "assistant", "content": answer})
        await reply_long(update, answer)
    except FileSecurityError as exc:
        await update.message.reply_text(f"Файл отклонён: {exc}")
    except Exception as exc:
        log.exception("handle_photo failed")
        await update.message.reply_text("Не удалось обработать изображение.")
        await notify_admins(context, f"critical handle_photo: {exc}")
    finally:
        cleanup_path(path)

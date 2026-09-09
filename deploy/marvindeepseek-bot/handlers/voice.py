"""Voice message handler."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config import DOWNLOADS_DIR, MAX_FILES_PER_DAY
from handlers.common import (
    allowed,
    bump_file_quota,
    cleanup_path,
    file_quota_ok,
    history,
    notify_admins,
    reply_long,
)
from services.audio_parser import transcribe_voice
from services.llm_service import LLMService

log = logging.getLogger("marvindeepseek.voice")
llm = LLMService()


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.voice:
        return
    user = update.effective_user
    if not allowed(user.id if user else None):
        await update.message.reply_text("Доступ ограничен.")
        return
    if not file_quota_ok(context, user.id):
        await update.message.reply_text(
            f"Дневной лимит файлов/голосовых исчерпан ({MAX_FILES_PER_DAY}/день)."
        )
        return

    voice = update.message.voice
    path: Path | None = None
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        tg_file = await context.bot.get_file(voice.file_id)
        path = DOWNLOADS_DIR / f"voice_{uuid.uuid4().hex[:10]}.ogg"
        await tg_file.download_to_drive(custom_path=str(path))
        bump_file_quota(context)

        text = transcribe_voice(str(path), language="ru-RU")
        if not text:
            await update.message.reply_text(
                "Не удалось распознать речь. Попробуйте говорить чётче или напишите текстом."
            )
            return

        await update.message.reply_text(f"Распознано: {text}")
        hist = history[update.effective_chat.id]
        hist.append({"role": "user", "content": text})
        answer = await llm.generate_response(text, history=list(hist))
        hist.append({"role": "assistant", "content": answer})
        await reply_long(update, answer)
    except Exception as exc:
        log.exception("handle_voice failed")
        await update.message.reply_text(
            "Ошибка обработки голосового сообщения. Нужны ffmpeg и доступ к Speech API."
        )
        await notify_admins(context, f"critical handle_voice: {exc}")
    finally:
        cleanup_path(path)

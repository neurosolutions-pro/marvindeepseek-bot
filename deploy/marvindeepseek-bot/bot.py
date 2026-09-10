"""MarvinDeepSeekBot entrypoint: DeepSeek + Memory MCP + files/voice generation."""

from __future__ import annotations

import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from threading import Thread

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import (
    LOGS_DIR,
    MEMORY_MCP_ENABLED,
    MEMORY_MCP_URL,
    PORT,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHUNK_LIMIT,
)
from handlers.commands import (
    cmd_clear,
    cmd_file,
    cmd_help,
    cmd_memory,
    cmd_remember,
    cmd_start,
    cmd_status,
)
from handlers.files import handle_document, handle_photo
from handlers.text import handle_prompt_format_callback, handle_text
from handlers.voice import handle_voice
from services import memory_service

LOG_FILE = LOGS_DIR / "bot.log"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("marvindeepseek")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.ExtBot").setLevel(logging.WARNING)
    return logger


log = setup_logging()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("", "/health"):
            mem = b"true" if memory_service.memory_client() else b"false"
            body = (
                b'{"status":"ok","service":"marvindeepseek-bot","memory":'
                + mem
                + b',"files":true}'
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        log.debug("health: " + fmt, *args)


def start_health_server() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    log.info("Health server on :%s", PORT)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")
    start_health_server()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("file", cmd_file))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("remember", cmd_remember))
    app.add_handler(CallbackQueryHandler(handle_prompt_format_callback, pattern=r"^prompt_fmt:"))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info(
        "Starting MarvinDeepSeekBot memory=%s url=%s chunk_limit=%s files=on",
        "on" if MEMORY_MCP_ENABLED else "off",
        MEMORY_MCP_URL if MEMORY_MCP_ENABLED else "-",
        TELEGRAM_CHUNK_LIMIT,
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()

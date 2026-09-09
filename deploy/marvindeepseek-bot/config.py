"""Configuration for MarvinDeepSeekBot (env-driven, no secrets in code)."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"
FONTS_DIR = BASE_DIR / "fonts"

for _d in (DOWNLOADS_DIR, LOGS_DIR, FONTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"].strip()
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL",
    f"{DEEPSEEK_API_BASE}/chat/completions",
).strip()
DEEPSEEK_API_MODEL = os.getenv("DEEPSEEK_API_MODEL", "deepseek-chat").strip()

PORT = int(os.getenv("PORT", "8082"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "12"))
TELEGRAM_CHUNK_LIMIT = int(os.getenv("TELEGRAM_CHUNK_LIMIT", "3500"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(20 * 1024 * 1024)))
MAX_FILES_PER_DAY = int(os.getenv("MAX_FILES_PER_DAY", "30"))

MEMORY_MCP_ENABLED = os.getenv("MEMORY_MCP_ENABLED", "1").strip() not in {
    "0",
    "false",
    "False",
    "",
}
MEMORY_MCP_URL = os.getenv("MEMORY_MCP_URL", "http://memory-mcp:3000/mcp").strip()
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "").strip()

_raw_users = os.getenv("ALLOWED_USERS", "").strip()
ALLOWED_USERS = {
    int(x) for x in _raw_users.replace(";", ",").split(",") if x.strip().isdigit()
}

_raw_admins = os.getenv("ADMIN_CHAT_IDS", os.getenv("ADMIN_CHAT_ID", "")).strip()
ADMIN_CHAT_IDS = {
    int(x) for x in _raw_admins.replace(";", ",").split(",") if x.strip().isdigit()
}

DEFAULT_SYSTEM_PROMPT = """Ты — MarvinDeepSeekBot: универсальный помощник по ИИ-агентам, ИИ-сервисам и контент-фабрикам.
Правила:
1. Всегда отвечай ПОЛНЫМ текстом. Запрещено обрывать ответ на «Часть 1 из N», «продолжение следует» или «…».
2. Не имитируй разбиение сообщений Telegram — транспорт сам отправит несколько сообщений.
3. Сначала предпочитай open-source/бесплатные решения.
4. Отвечай на языке пользователя.
5. Для сложных тем используй заголовки, списки/таблицы и блоки кода.
6. Будь практичным и честным; не предлагай пиратство, взлом API или обход лицензий.
7. Если дан блок «Память», используй эти факты. Не выдумывай память, которой нет.
"""
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT).strip() or DEFAULT_SYSTEM_PROMPT

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".txt",
    ".md",
    ".zip",
}

DEJAVU_CANDIDATES = [
    str(FONTS_DIR / "DejaVuSans.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]

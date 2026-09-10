# MarvinDeepSeekBot

Telegram-бот на DeepSeek API с памятью (Memory MCP), приёмом файлов, OCR, голосовыми сообщениями и генерацией PDF/Word/Excel.

## Возможности

- Текст ↔ DeepSeek + история диалога
- Долговременная память через `memory-mcp`
- Файлы: PDF, Word, Excel/CSV, изображения (OCR), TXT/MD, ZIP
- Голосовые сообщения (ffmpeg + SpeechRecognition)
- Генерация ответов в PDF / DOCX / XLSX
- Уточнение формата для промтов (inline-кнопки Текст/PDF)
- Сплит длинных ответов под лимит Telegram
- Allowlist пользователей, дневной лимит файлов, базовая проверка magic bytes

## Структура

```text
deploy/marvindeepseek-bot/
  bot.py
  config.py
  handlers/
  services/
  fonts/
  downloads/
  logs/
  Dockerfile
  docker-compose.yml
  requirements.txt
  setup.sh / setup.bat
```

## Установка (локально)

### Linux / macOS

```bash
cd deploy/marvindeepseek-bot
chmod +x setup.sh
./setup.sh
# отредактируйте .env
source .venv/bin/activate
python bot.py
```

Системные пакеты (рекомендуется):

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-rus ffmpeg fonts-dejavu-core
```

### Windows

```bat
cd deploy\marvindeepseek-bot
setup.bat
:: заполните .env
.venv\Scripts\activate
python bot.py
```

Установите [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) с языками `rus`+`eng` и ffmpeg в PATH.

## Docker (production)

```bash
cd deploy/marvindeepseek-bot
cp .env.example .env   # заполнить токены
docker network create agent-shared || true
docker compose up -d --build
curl http://127.0.0.1:8082/health
```

Бот ожидает `memory-mcp` в сети `agent-shared` (`MEMORY_MCP_URL=http://memory-mcp:3000/mcp`).

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен BotFather |
| `HERMES_BASE_URL` / `HERMES_API_KEY` | OpenAI-совместимый шлюз Hermes (приоритет) |
| `HERMES_MODEL` | модель через Hermes (по умолчанию `deepseek-chat`) |
| `DEEPSEEK_API_KEY` | ключ DeepSeek (fallback, если Hermes не задан) |
| `ALLOWED_USERS` | CSV Telegram user id |
| `ADMIN_CHAT_IDS` | куда слать critical errors |
| `MEMORY_MCP_*` / `MCP_AUTH_TOKEN` | память |
| `MAX_FILE_SIZE` | байты, по умолчанию 20 МБ |
| `MAX_FILES_PER_DAY` | лимит файлов/голосовых на пользователя |

## Команды

- `/start` `/help` `/status` `/digest` `/cursor_prompt` `/file`
- `/status` — активная LLM и подключения (Hermes gateway, memory-mcp, DeepSeek)
- `/digest <тема>` — сводка с выбором формата (короткий/отчёт/таблица/markdown/JSON)
- `/cursor_prompt <задача>` — промт для Cursor (один большой или серия итераций)
- `/clear` — очистить историю чата
- `/memory` `/remember <факт>`

## Примеры тестов

1. Текст: «Объясни CrewAI кратко»
2. Промт: «Составь промт для генерации SEO-статьи» → кнопка Текст или PDF
3. Excel: «Сделай таблицу сравнения n8n и Make»
4. Файл: отправить `sample.pdf` с подписью «Суммируй»
5. Фото с текстом: OCR + анализ
6. Голосовое: короткое сообщение на русском
7. ZIP с `.txt` внутри

## Troubleshooting

| Проблема | Решение |
|---|---|
| PDF с кракозябрами | положите `fonts/DejaVuSans.ttf` или установите `fonts-dejavu-core` |
| OCR не работает | установите `tesseract-ocr-rus` |
| Голос не распознаётся | нужен `ffmpeg`; проверьте сеть до Google Speech |
| «Доступ ограничен» | добавьте user id в `ALLOWED_USERS` |
| memory:false | проверьте сеть `agent-shared` и `MCP_AUTH_TOKEN` |
| Файл отклонён | проверьте расширение/magic bytes/размер |

## Логи

Ротация: `logs/bot.log` (RotatingFileHandler).

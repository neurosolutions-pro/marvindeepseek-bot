# INTEGRATION_LOG — Hermes + MarvinDeepSeekBot

Дата: 2026-09-10  
Проект: `/workspace/hermes-integration`

## Шаг 1. Разведка окружения

| Компонент | Результат |
|-----------|-----------|
| Python | 3.12.3 (`python3`; `python` отсутствовал) |
| pip | 24.0 → обновлён в venv до 26.2.1 |
| Docker | **не установлен** в среде → стек запускается через venv + nohup; `docker-compose.yml` подготовлен |
| Node | v22.14.0 |
| Порт 8000 / 8001 | свободны на момент разведки |
| Ollama | не установлен |

### Выбор пакета Hermes

Проверено:

- `pip index versions hermes` → **HERMES (DLR)** — публикация research software metadata, **не LLM**.
- `npm view hermes` → Segment chat bot (устарел), **не LLM**.
- GitHub / PyPI → **`hermes-agent` (Nous Research)**, MIT, активно поддерживается (версия **0.19.0** на 2026-09-10), OpenAI-совместимый API server / gateway.

**Выбран:** `hermes-agent==0.19.0` (MIT).

## Шаг 2. Установка

```text
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # включает hermes-agent==0.19.0
```

Изоляция: `./hermes-integration/.venv/`.  
Нативная конфигурация Hermes Agent: `HERMES_HOME=./.hermes` (синхронизируется скриптом `scripts/apply_config.py`).

Альтернатива без Docker: локальный OpenAI-совместимый upstream (`local_upstream.py`) как бесплатная offline-модель `hermes-local-mock`.

## Шаг 3. Конфигурация

Файлы:

| Файл | Назначение |
|------|------------|
| `.env` | секреты: `HERMES_API_KEY`, URL, upstream key (**gitignore**) |
| `hermes.config.yaml` | host `0.0.0.0`, port `8000`, model, log_level (**gitignore**) |
| `.hermes/config.yaml` + `.hermes/.env` | native hermes-agent home |
| `hermes_server.py` | OpenAI gateway на :8000 (`/health`, `/v1/models`, `/v1/chat/completions`) |
| `local_upstream.py` | бесплатный upstream на :8001 |

Запуск: `make run` → health: `curl http://127.0.0.1:8000/health`.

## Шаг 4. Бот-клиент MarvinDeepSeekBot

| Файл | Назначение |
|------|------------|
| `bot_client.py` | клиент с ретраями (timeout/401/429/5xx, экспоненциальная задержка), лог `bot_client.log` |
| `bot_config.yaml` | system_prompt, max_tokens=2048, temperature=0.7 |
| `test_bot_client.py` | один запрос → проверка непустого ответа |

## Шаг 5. Автозапуск и проверка

- `docker-compose.yml` — сервисы `upstream`, `hermes`, `bot` (профиль `bot`)
- `Makefile` — `install`, `run`, `stop`, `test`, `logs`, `health`, `bot`

### Как запустить

```bash
cd hermes-integration
make install   # один раз
make run
make test
# или: make bot MSG='Привет'
```

### Как остановить

```bash
make stop
```

### Как поменять модель

1. Поставить Ollama / vLLM / другой OpenAI endpoint.
2. В `.env` задать:
   - `HERMES_UPSTREAM_BASE_URL=http://127.0.0.1:11434/v1`
   - `HERMES_UPSTREAM_API_KEY=ollama` (или реальный ключ)
   - `HERMES_MODEL=<id модели>`
3. Обновить `model:` в `hermes.config.yaml` и `bot_config.yaml`.
4. `make stop && make run`.

Для native API server Hermes Agent: `hermes gateway run` с `API_SERVER_*` из `.hermes/.env` (после `scripts/apply_config.py`). В этой среде основной путь — `hermes_server.py` (стабильный OpenAI proxy поверх hermes-agent deps + upstream).

### Где логи и ключи

| Что | Где |
|-----|-----|
| API key | `.env` → `HERMES_API_KEY` |
| Gateway logs | `logs/hermes_gateway.log`, `logs/hermes.stdout.log` |
| Upstream logs | `logs/upstream.stdout.log` |
| Bot client logs | `bot_client.log` |
| Hermes Agent home | `.hermes/` |

## Итоговая схема

```text
MarvinDeepSeekBot (bot_client.py)
        │  Authorization: Bearer HERMES_API_KEY
        ▼
Hermes Gateway :8000  (hermes_server.py, OpenAI /v1/*)
        │
        ▼
Local Upstream :8001  (local_upstream.py)  ← или Ollama/vLLM/cloud
```

Одна команда проверки: `cd hermes-integration && make test`

## Верификация (2026-09-10)

- `curl http://127.0.0.1:8000/health` → `status=ok`, `upstream_ok=true`
- `GET /v1/models` с неверным ключом → `401 Unauthorized`
- `python bot_client.py` → ответ 200 с текстом MarvinDeepSeekBot / Hermes
- `make test` → `PASS: test_bot_client_receives_response`
- `hermes version` → Hermes Agent v0.19.0
- Docker в среде отсутствует → использован venv-стек; compose-файл готов для локальных машин

## Timeweb deploy (лёгкий шлюз, 2026-09-10)

Сервер: `neurosolutions-app1` (`72.56.18.124`, nl-1/ams-1)

| Параметр | Значение |
|----------|----------|
| Путь | `/opt/my_services/hermes` |
| Контейнер | `hermes` (slim, mem_limit 256m) |
| Порт | `127.0.0.1:8000` |
| Upstream | DeepSeek API (`HERMES_UPSTREAM_BASE_URL`) |
| Сеть | `agent-shared` → доступно как `http://hermes:8000` |
| Факт. RAM | ~50 MiB |
| Compose | `deploy/timeweb/docker-compose.yml` |

Проверка на VPS:

```bash
curl -sS http://127.0.0.1:8000/health
docker exec marvindeepseek-bot python -c "import urllib.request; print(urllib.request.urlopen('http://hermes:8000/health').read().decode())"
```

Секреты: `/opt/my_services/hermes/deploy/timeweb/.env` (`HERMES_API_KEY`, upstream key).

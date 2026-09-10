# Timeweb lightweight Hermes deploy

Один контейнер `hermes` (OpenAI-совместимый шлюз) → upstream DeepSeek API.
Без локальной модели / без Ollama.

## На сервере

```bash
cd /opt/my_services/hermes
# .env уже должен содержать HERMES_API_KEY и HERMES_UPSTREAM_API_KEY
docker network create agent-shared || true
docker compose up -d --build
curl -sS http://127.0.0.1:8000/health
```

Внутренний URL для ботов в сети `agent-shared`: `http://hermes:8000`

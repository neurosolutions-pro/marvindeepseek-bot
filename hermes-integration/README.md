# Hermes Integration (MarvinDeepSeekBot)

Open-source связка **NousResearch Hermes Agent (`hermes-agent`)** + OpenAI-совместимый шлюз + клиент MarvinDeepSeekBot.

## Быстрый старт

```bash
cd hermes-integration
cp .env.example .env          # задайте HERMES_API_KEY
cp hermes.config.example.yaml hermes.config.yaml
make install
make run
make test
```

Проверка одной командой:

```bash
make test
```

Health: `curl http://127.0.0.1:8000/health`

Подробный журнал шагов: [`INTEGRATION_LOG.md`](./INTEGRATION_LOG.md).

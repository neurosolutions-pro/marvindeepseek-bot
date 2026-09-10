# Agent skills & rules package

This repository includes a practical package for:

1. Web research (with source discipline)
2. Digests/reports
3. Cursor prompt generation

## Files
| Path | Purpose |
|------|---------|
| [`AGENTS.md`](../AGENTS.md) | Top-level agent contract |
| [`.cursor/skills.yaml`](../.cursor/skills.yaml) | Skills map |
| [`.cursor/rules/research_digest_cursor.mdc`](../.cursor/rules/research_digest_cursor.mdc) | Always-on rules |
| [`.cursor/templates/`](../.cursor/templates/) | Prompt templates |
| Telegram `/digest`, `/cursor_prompt`, `/status` | Runtime commands in MarvinDeepSeekBot |

## Telegram usage
```text
/digest Сравнение SearxNG и DuckDuckGo для агентов
→ выбрать формат кнопкой

/cursor_prompt Добавь /health в FastAPI и pytest
→ выбрать: один промт или серия итераций

/status
→ LLM + Hermes + MCP
```

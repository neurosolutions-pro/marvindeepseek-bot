"""Digest/report builder for /digest command."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.llm_service import LLMService

DIGEST_FORMATS = {
    "short": "короткий дайджест (5–10 строк + источники)",
    "report": "структурный отчёт",
    "table": "сравнительная таблица + краткие выводы",
    "markdown": "развёрнутый Markdown-отчёт",
    "json": "строгий JSON по схеме digest",
}

JSON_SCHEMA_HINT = """
Верни ТОЛЬКО валидный JSON:
{
  "tldr": ["..."],
  "key_points": ["..."],
  "details": ["..."],
  "sources": [{"title":"...","url":"...","date":"..."}],
  "risks": ["..."],
  "recommendations": ["..."]
}
""".strip()


def build_digest_prompt(topic: str, fmt: str) -> str:
    fmt_label = DIGEST_FORMATS.get(fmt, DIGEST_FORMATS["markdown"])
    extra = JSON_SCHEMA_HINT if fmt == "json" else ""
    return f"""
Собери сводку по теме/запросу пользователя.

Тема:
{topic}

Формат вывода: {fmt_label}

Обязательные разделы (если формат не JSON):
1) TL;DR
2) Ключевые пункты
3) Детали (по необходимости)
4) Источники (если точных URL нет — честно напиши, что нужны проверки по docs/GitHub/новостям; не выдумывай ссылки)
5) Риски / неопределённости
6) Рекомендации / следующие шаги

Правила:
- Язык: русский; технические термины без перевода оставляй как есть.
- Не выдумывай факты, цифры, URL и даты.
- Если данных недостаточно — явно укажи пробелы.
- Экономь воду, сохраняй точность.
- Open-source/бесплатные решения в приоритете.

{extra}
""".strip()


async def generate_digest(topic: str, fmt: str, *, llm: "LLMService | None" = None) -> str:
    from services.llm_service import LLMService

    client = llm or LLMService()
    return await client.generate_response(
        build_digest_prompt(topic, fmt),
        temperature=0.4,
    )

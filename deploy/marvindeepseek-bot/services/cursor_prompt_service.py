"""Cursor prompt generator for /cursor_prompt command."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.llm_service import LLMService

PROMPT_MODES = {
    "single": "один большой самодостаточный промт",
    "iterative": "серия из 3–5 коротких итеративных промтов (шаг за шагом)",
}


def build_cursor_prompt_request(task: str, mode: str) -> str:
    mode_label = PROMPT_MODES.get(mode, PROMPT_MODES["single"])
    return f"""
Сгенерируй готовый промт (или серию промтов) для AI-агента Cursor.

Задача пользователя:
{task}

Режим: {mode_label}

Требования к результату:
- Язык промта: русский (термины/имена файлов/команды — как принято в разработке).
- Стек по умолчанию, если не указан: Python 3.11+, pytest, ruff.
- Если уместно, включи: цель, контекст/файлы (плейсхолдеры путей), ограничения,
  DoD (критерии готовности), тесты/проверки, формат результата.
- Не добавляй платные SaaS без необходимости; предпочитай open-source.
- Не предлагай деструктивные действия без явного подтверждения.
- Верни только готовый текст промта(ов), без предисловий.
- Если режим iterative: пронумеруй шаги 1..N, каждый шаг самодостаточен.
""".strip()


async def generate_cursor_prompt(
    task: str, mode: str, *, llm: "LLMService | None" = None
) -> str:
    from services.llm_service import LLMService

    client = llm or LLMService()
    return await client.generate_response(
        build_cursor_prompt_request(task, mode),
        temperature=0.35,
    )

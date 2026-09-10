"""LLM client (Hermes gateway preferred, DeepSeek fallback)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import LLM_API_KEY, LLM_API_MODEL, LLM_API_URL, LLM_PROVIDER, SYSTEM_PROMPT

log = logging.getLogger("marvindeepseek.llm")


class LLMService:
    """Async OpenAI-compatible chat completions client."""

    def __init__(
        self,
        *,
        api_url: str = LLM_API_URL,
        api_key: str = LLM_API_KEY,
        model: str = LLM_API_MODEL,
        system_prompt: str = SYSTEM_PROMPT,
        provider: str = LLM_PROVIDER,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.provider = provider
        log.info("LLM provider=%s model=%s url=%s", self.provider, self.model, self.api_url)

    async def generate_response(
        self,
        prompt: str,
        *,
        memory_block: str = "",
        history: list[dict[str, str]] | None = None,
        temperature: float = 0.7,
    ) -> str:
        system = self.system_prompt
        if memory_block:
            system = f"{self.system_prompt}\n\n# Память\n{memory_block}"

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        else:
            messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code >= 400:
                log.error(
                    "LLM error provider=%s status=%s body=%s",
                    self.provider,
                    resp.status_code,
                    resp.text[:500],
                )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    async def generate_excel_rows(self, prompt: str) -> list[list[str]]:
        """Ask LLM for TSV table rows suitable for Excel."""
        instruction = (
            "Составь ответ ТОЛЬКО как TSV-таблицу: первая строка — заголовки, "
            "далее строки данных. Без markdown и пояснений.\n\nЗадача:\n"
            f"{prompt}"
        )
        raw = await self.generate_response(instruction, temperature=0.2)
        rows: list[list[str]] = []
        for line in raw.splitlines():
            line = line.strip().strip("`")
            if not line or line.startswith("---"):
                continue
            if "\t" in line:
                rows.append([c.strip() for c in line.split("\t")])
            elif "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if cells and not set(cells[0]) <= {"-"}:
                    rows.append(cells)
            else:
                rows.append([line])
        return rows or [["Результат"], [raw[:2000]]]

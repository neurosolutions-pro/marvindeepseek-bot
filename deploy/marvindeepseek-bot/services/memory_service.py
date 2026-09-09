"""Persistent Memory MCP client (Streamable HTTP)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import MCP_AUTH_TOKEN, MEMORY_MCP_ENABLED, MEMORY_MCP_URL

log = logging.getLogger("marvindeepseek.memory")


class MemoryMCPClient:
    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self.token = token
        self.session_id: str | None = None
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            headers["x-api-key"] = self.token
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    @staticmethod
    def _parse_sse_or_json(raw: str) -> dict[str, Any]:
        raw = raw.strip()
        if not raw:
            return {}
        if raw.startswith("{") or raw.startswith("["):
            data = json.loads(raw)
            return data if isinstance(data, dict) else {"result": data}
        payload = None
        for line in raw.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
        if not payload:
            raise RuntimeError(f"empty SSE payload: {raw[:200]}")
        data = json.loads(payload)
        return data if isinstance(data, dict) else {"result": data}

    async def _post(self, body: dict[str, Any], *, expect_json: bool = True) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.url, headers=self._headers(), json=body)
            sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            if resp.status_code >= 400:
                raise RuntimeError(f"MCP HTTP {resp.status_code}: {resp.text[:300]}")
            if not expect_json or not resp.content:
                return {}
            return self._parse_sse_or_json(resp.text)

    async def ensure_session(self) -> None:
        if self.session_id:
            return
        await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "marvindeepseek-bot", "version": "1.2.0"},
                },
            }
        )
        await self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            expect_json=False,
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        await self.ensure_session()
        data = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in data:
            raise RuntimeError(str(data["error"]))
        result = data.get("result", data)
        if isinstance(result, dict) and "content" in result:
            texts = []
            for item in result.get("content") or []:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text") or "")
            joined = "\n".join(texts).strip()
            if not joined:
                return result
            try:
                return json.loads(joined)
            except json.JSONDecodeError:
                return joined
        return result

    async def search(self, query: str) -> Any:
        return await self.call_tool("search_nodes", {"query": query})

    async def open_nodes(self, names: list[str]) -> Any:
        return await self.call_tool("open_nodes", {"names": names})

    async def create_entities(self, entities: list[dict[str, Any]]) -> Any:
        return await self.call_tool("create_entities", {"entities": entities})

    async def add_observations(self, observations: list[dict[str, Any]]) -> Any:
        return await self.call_tool("add_observations", {"observations": observations})

    async def health(self) -> bool:
        health_url = self.url.rsplit("/mcp", 1)[0] + "/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(health_url)
                return resp.status_code == 200
        except Exception:
            return False


_memory: MemoryMCPClient | None = None
if MEMORY_MCP_ENABLED:
    _memory = MemoryMCPClient(MEMORY_MCP_URL, MCP_AUTH_TOKEN)


def memory_client() -> MemoryMCPClient | None:
    return _memory


def user_entity(user_id: int) -> str:
    return f"telegram-user:{user_id}"


def format_memory_block(data: Any) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data.strip()
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except TypeError:
        text = str(data)
    text = text.strip()
    if not text or text in {"[]", "{}", "null"}:
        return ""
    if len(text) > 2500:
        text = text[:2500] + "\n…"
    return text


async def load_memory_context(user_id: int, query: str) -> str:
    client = memory_client()
    if not client:
        return ""
    try:
        parts: list[str] = []
        profile = await client.open_nodes([user_entity(user_id)])
        block = format_memory_block(profile)
        if block:
            parts.append(f"Профиль пользователя:\n{block}")
        searched = await client.search(query[:200] if query else f"user {user_id}")
        sblock = format_memory_block(searched)
        if sblock and sblock != block:
            parts.append(f"Релевантная память:\n{sblock}")
        return "\n\n".join(parts)
    except Exception:
        log.exception("memory load failed")
        return ""


async def ensure_user_entity(user_id: int, display_name: str | None = None) -> None:
    client = memory_client()
    if not client:
        return
    name = user_entity(user_id)
    observations = [f"telegram_id:{user_id}"]
    if display_name:
        observations.append(f"name:{display_name}")
    try:
        existing = await client.open_nodes([name])
        empty = (
            existing in (None, [], {}, "")
            or (isinstance(existing, dict) and not existing.get("entities"))
            or (isinstance(existing, list) and len(existing) == 0)
        )
        if empty:
            await client.create_entities(
                [{"name": name, "entityType": "Person", "observations": observations}]
            )
        elif display_name:
            await client.add_observations(
                [{"entityName": name, "contents": [f"name:{display_name}"]}]
            )
    except Exception:
        log.exception("ensure_user_entity failed")


async def remember_fact(user_id: int, fact: str) -> str:
    client = memory_client()
    if not client:
        return "Память отключена."
    fact = fact.strip()
    if not fact:
        return "Пустой факт — ничего не сохранил."
    await ensure_user_entity(user_id)
    await client.add_observations(
        [{"entityName": user_entity(user_id), "contents": [f"fact:{fact}"]}]
    )
    return f"Запомнил: {fact}"


async def remember_turn(user_id: int, user_text: str, answer: str) -> None:
    client = memory_client()
    if not client:
        return
    try:
        await ensure_user_entity(user_id)
        note = f"Q: {user_text[:240]} | A: {answer[:240]}".replace("\n", " ")
        await client.add_observations(
            [{"entityName": user_entity(user_id), "contents": [f"dialog:{note}"]}]
        )
    except Exception:
        log.exception("remember_turn failed")

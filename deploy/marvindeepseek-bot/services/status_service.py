"""Runtime status for /status: active LLM + connected MCP/backends."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import (
    DEEPSEEK_API_BASE,
    DEEPSEEK_API_KEY,
    HERMES_API_KEY,
    HERMES_BASE_URL,
    LLM_API_BASE,
    LLM_API_MODEL,
    LLM_API_URL,
    LLM_PROVIDER,
    MEMORY_MCP_ENABLED,
    MEMORY_MCP_URL,
)
from services import memory_service

log = logging.getLogger("marvindeepseek.status")


async def _probe_http(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers or {})
            body: Any = None
            try:
                body = resp.json()
            except Exception:
                body = (resp.text or "")[:200]
            return {
                "ok": resp.status_code < 400,
                "status_code": resp.status_code,
                "body": body,
            }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status_code": None, "error": str(exc)}


async def probe_hermes() -> dict[str, Any]:
    if not (HERMES_BASE_URL and HERMES_API_KEY):
        return {
            "name": "hermes",
            "kind": "llm-gateway",
            "configured": False,
            "reachable": False,
            "detail": "не настроен (HERMES_BASE_URL / HERMES_API_KEY)",
        }
    health = await _probe_http(f"{HERMES_BASE_URL}/health")
    models = await _probe_http(
        f"{HERMES_BASE_URL}/v1/models",
        headers={"Authorization": f"Bearer {HERMES_API_KEY}"},
    )
    body = health.get("body") if isinstance(health.get("body"), dict) else {}
    upstream = ""
    if isinstance(body, dict):
        upstream = str(body.get("upstream_base_url") or "")
        upstream_ok = body.get("upstream_ok")
    else:
        upstream_ok = None
    reachable = bool(health.get("ok") or models.get("ok"))
    detail_parts = [
        f"url={HERMES_BASE_URL}",
        f"health={'ok' if health.get('ok') else 'down'}",
        f"models={'ok' if models.get('ok') else 'down'}",
    ]
    if upstream:
        detail_parts.append(f"upstream={upstream}")
        if upstream_ok is not None:
            detail_parts.append(f"upstream_ok={upstream_ok}")
    return {
        "name": "hermes",
        "kind": "llm-gateway",
        "configured": True,
        "reachable": reachable,
        "active_llm_path": LLM_PROVIDER == "hermes",
        "detail": "; ".join(detail_parts),
        "upstream_base_url": upstream,
        "upstream_ok": upstream_ok,
    }


async def probe_memory_mcp() -> dict[str, Any]:
    if not MEMORY_MCP_ENABLED:
        return {
            "name": "memory-mcp",
            "kind": "mcp",
            "configured": False,
            "reachable": False,
            "detail": "выключен (MEMORY_MCP_ENABLED=0)",
        }
    client = memory_service.memory_client()
    if not client:
        return {
            "name": "memory-mcp",
            "kind": "mcp",
            "configured": True,
            "reachable": False,
            "detail": f"url={MEMORY_MCP_URL}; клиент не создан",
        }
    ok = await client.health()
    return {
        "name": "memory-mcp",
        "kind": "mcp",
        "configured": True,
        "reachable": ok,
        "detail": f"url={MEMORY_MCP_URL}; health={'ok' if ok else 'down'}",
    }


async def probe_deepseek_direct() -> dict[str, Any]:
    """Direct DeepSeek availability (fallback path / Hermes upstream identity)."""
    configured = bool(DEEPSEEK_API_KEY)
    if not configured:
        return {
            "name": "deepseek",
            "kind": "llm-provider",
            "configured": False,
            "reachable": False,
            "detail": "ключ не задан",
        }
    # Do not call DeepSeek with Hermes key; only report config when Hermes is active.
    if LLM_PROVIDER == "hermes":
        return {
            "name": "deepseek",
            "kind": "llm-provider",
            "configured": True,
            "reachable": None,
            "detail": f"используется как upstream через Hermes; base={DEEPSEEK_API_BASE}",
            "role": "hermes-upstream",
        }
    # DEEPSEEK_API_BASE is usually https://api.deepseek.com (without /v1).
    probe_url = f"{DEEPSEEK_API_BASE.rstrip('/')}/v1/models"
    result = await _probe_http(
        probe_url,
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
    )
    return {
        "name": "deepseek",
        "kind": "llm-provider",
        "configured": True,
        "reachable": bool(result.get("ok")),
        "detail": f"direct base={DEEPSEEK_API_BASE}; models={'ok' if result.get('ok') else 'down'}",
        "role": "direct",
    }


def _mark(ok: bool | None) -> str:
    if ok is True:
        return "✅"
    if ok is False:
        return "❌"
    return "➖"


async def build_status_report() -> str:
    hermes = await probe_hermes()
    memory = await probe_memory_mcp()
    deepseek = await probe_deepseek_direct()

    lines = [
        "📊 Статус MarvinDeepSeekBot",
        "",
        "🧠 Активная LLM",
        f"• provider: `{LLM_PROVIDER}`",
        f"• model: `{LLM_API_MODEL}`",
        f"• endpoint: `{LLM_API_URL}`",
        f"• base: `{LLM_API_BASE}`",
        "",
        "🔌 Подключения",
    ]

    for item in (hermes, memory, deepseek):
        configured = item.get("configured")
        reachable = item.get("reachable")
        active = item.get("active_llm_path")
        role = item.get("role")
        mark = _mark(reachable if configured else False)
        extra = ""
        if active:
            extra = " ← активный путь LLM"
        elif role == "hermes-upstream":
            extra = " ← upstream Hermes"
        lines.append(
            f"{mark} `{item['name']}` ({item['kind']})"
            f"{' [не настроен]' if not configured else ''}{extra}"
        )
        lines.append(f"   {item.get('detail')}")

    # Summary counts
    mcp_ok = 1 if memory.get("reachable") else 0
    mcp_total = 1 if memory.get("configured") else 0
    gateway_ok = 1 if hermes.get("reachable") else 0
    lines.extend(
        [
            "",
            "📈 Сводка",
            f"• MCP online: {mcp_ok}/{mcp_total} (memory-mcp)",
            f"• Hermes gateway: {'online' if gateway_ok else 'offline/не настроен'}",
            f"• DeepSeek: "
            + (
                "через Hermes (upstream)"
                if deepseek.get("role") == "hermes-upstream"
                else ("direct online" if deepseek.get("reachable") else "direct offline/не задан")
            ),
        ]
    )
    return "\n".join(lines)

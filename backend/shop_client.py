"""The backend's MCP client for human/admin actions and dashboard reads.

There is no second shop-data layer: this calls the same campus-customs MCP
server the agents use, including the HUMAN_ONLY tools no agent is given.
The FastAPI app keeps one connection open (open()/close() in its lifespan);
the CLI falls back to a short-lived connection per call.
"""

import asyncio
from typing import Any

from fastmcp import Client

from .config import mcp_client_config

_client: Client | None = None
_lock = asyncio.Lock()


def _new_client() -> Client:
    return Client(mcp_client_config())


async def open() -> None:
    global _client
    async with _lock:
        if _client is None:
            _client = _new_client()
            await _client.__aenter__()


async def close() -> None:
    global _client
    async with _lock:
        if _client is not None:
            await _client.__aexit__(None, None, None)
            _client = None


def _unwrap(result) -> Any:
    return result.structured_content if result.structured_content is not None else result.data


async def call_tool(name: str, args: dict[str, Any] | None = None) -> Any:
    if _client is not None:
        return _unwrap(await _client.call_tool(name, args or {}))
    async with _new_client() as client:
        return _unwrap(await client.call_tool(name, args or {}))


async def decide(approval_id: int, decision: str, approver: str, note: str = "") -> dict:
    """A human approves or rejects. If approved, execute it right away through MCP:
    payments move cash (pay_approved_request); purchase orders are placed as vendor drafts."""
    out = {"decision": await call_tool("decide_approval", {
        "approval_id": approval_id, "decision": decision, "approver": approver, "note": note})}
    if decision == "approved" and "error" not in out["decision"]:
        kind = next((a["kind"] for a in (await call_tool("list_approvals"))["approvals"]
                     if a["id"] == approval_id), None)
        if kind == "payment":
            out["executed"] = await call_tool("pay_approved_request", {"approval_id": approval_id})
        elif kind == "purchase_order":
            out["executed"] = await call_tool("place_approved_purchase_order", {"approval_id": approval_id})
    return out

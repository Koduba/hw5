"""FastAPI backend for the Campus Customs dashboard.

Every shop fact and every change goes through the campus-customs MCP server
(backend/shop_client.py for human actions, the agents' MCPToolset for runs).

Start it either way (http://localhost:8000, docs at /docs):
    cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000
    .venv/bin/python -m backend.main          # from hw5/, no reloader
"""

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# `uvicorn main:app` run from backend/ imports this file as a top-level module, so make
# hw5/ importable and load the rest of the backend as the `backend` package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import shop_client  # noqa: E402
from backend.config import AUDIT_FILE, MODEL_NAME  # noqa: E402
from backend.models import TeamRunResult  # noqa: E402
from backend.team import run_ticket  # noqa: E402

# One team run at a time: runs share one cash balance and one token budget.
_run_lock = asyncio.Lock()
_runs: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await shop_client.open()  # one long-lived MCP connection for dashboard reads/actions
    try:
        yield
    finally:
        await shop_client.close()


app = FastAPI(title="Campus Customs Ops API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv(
        "DASHBOARD_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


async def mcp(tool: str, args: dict[str, Any] | None = None) -> Any:
    """Call an MCP tool; turn a tool-level {"error": ...} into an HTTP 4xx."""
    result = await shop_client.call_tool(tool, args)
    if isinstance(result, dict) and "error" in result:
        status = 404 if "does not exist" in str(result["error"]) else 409
        raise HTTPException(status, detail=result["error"])
    return result


# ------------------------------------------------------------------ models

class TicketRow(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    status: str = Field(description="Raw status: open, in_progress, waiting_on_human or resolved.")
    state: Literal["open", "resolved"] = Field(description="Simple view: anything not resolved is open.")
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    notes: str | None = None
    created_at: str


class RunInfo(BaseModel):
    run_id: str
    ticket_id: int
    status: Literal["running", "done", "error"]
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    resolved: bool | None = Field(None, description="True if the ticket was resolved when the run finished; "
                                                     "false if it is waiting on a human approval.")
    result: TeamRunResult | None = None


class Decision(BaseModel):
    approver: str = Field(min_length=1, description="The human's name, recorded as approved_by.")
    note: str = ""


# ------------------------------------------------------------------ 1. tickets

@app.get("/api/tickets", response_model=list[TicketRow], summary="All tickets, open or resolved")
async def tickets():
    data = await mcp("list_tickets")
    return [{**t, "state": "resolved" if t["status"] == "resolved" else "open"} for t in data["tickets"]]


@app.get("/api/tickets/{ticket_id}", summary="One ticket with everything it links to")
async def ticket(ticket_id: int):
    return await mcp("get_ticket", {"ticket_id": ticket_id})


# ------------------------------------------------------------------ 2. run the team

async def resolve_if_settled(ticket_id: int, by: str) -> bool:
    """Mark a ticket resolved once nothing on it still needs a human.

    Settled = no pending approvals, and no approved payment/PO left un-executed
    (an approved discount needs no execution). update_ticket itself also refuses
    to resolve while anything is pending, so this can't skip an approval.
    """
    t = (await mcp("get_ticket", {"ticket_id": ticket_id}))
    if t["ticket"]["status"] == "resolved":
        return True
    for a in t.get("approvals", []):
        if a["status"] == "pending" or (a["status"] == "approved" and a["kind"] != "discount"):
            return False
    await mcp("update_ticket", {"ticket_id": ticket_id, "status": "resolved", "author": by,
                                "note": "Run finished and nothing is waiting on a human."})
    return True


async def _run(run_id: str, ticket_id: int) -> None:
    info = _runs[run_id]
    async with _run_lock:
        try:
            info["result"] = await run_ticket(ticket_id, run_id=run_id)
            info["status"] = "done"
            if info["result"].output.final_status == "waiting_on_human":
                # The boss left a decision for a person. Respect it: the ticket resolves when its
                # approvals are decided, or when a person marks it resolved (POST .../resolve).
                info["resolved"] = False
            else:
                info["resolved"] = await resolve_if_settled(ticket_id, by="system")
        except Exception as exc:  # the audit trail already has the error step
            info.update(status="error", error=f"{type(exc).__name__}: {exc}")
        finally:
            info["finished_at"] = _now()


@app.post("/api/tickets/{ticket_id}/run", response_model=RunInfo, status_code=202,
          summary="Start the agent team on a ticket (returns at once; poll the run or the events)")
async def run(ticket_id: int):
    await mcp("get_ticket", {"ticket_id": ticket_id})  # 404 if the ticket doesn't exist
    if _run_lock.locked() or any(r["status"] == "running" for r in _runs.values()):
        raise HTTPException(409, detail="A team run is already in progress. Wait for it to finish.")
    run_id = uuid.uuid4().hex[:8]
    _runs[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running", "started_at": _now()}
    asyncio.create_task(_run(run_id, ticket_id))
    return _runs[run_id]


@app.post("/api/tickets/{ticket_id}/resolve", summary="A person closes a ticket the boss left for a human decision")
async def resolve(ticket_id: int, body: Decision):
    if _run_lock.locked():
        raise HTTPException(409, detail="A team run is in progress; resolve after it finishes.")
    note = body.note or f"Marked resolved by {body.approver.strip()} after reviewing the team's decision."
    return await mcp("update_ticket", {"ticket_id": ticket_id, "status": "resolved",
                                       "author": body.approver.strip(), "note": note})


@app.get("/api/runs", response_model=list[RunInfo], summary="Team runs started since the server began")
async def runs():
    return list(_runs.values())[::-1]


@app.get("/api/runs/{run_id}", response_model=RunInfo, summary="Status and final result of one run")
async def run_status(run_id: str):
    if run_id not in _runs:
        raise HTTPException(404, detail=f"Run {run_id} not found.")
    return _runs[run_id]


# ------------------------------------------------------------------ 3. agent events

def _summarize(e: dict[str, Any]) -> dict[str, Any]:
    """Turn one audit step into what the board shows: who, what they said, which tool."""
    d, kind = e.get("data", {}), e["kind"]
    said, tool, args = None, None, None
    if kind == "start":
        said = d.get("prompt")
    elif kind == "model_response":
        texts = [p["content"] for p in d.get("parts", []) if p["part"] == "text"]
        calls = [p.get("tool") for p in d.get("parts", []) if p["part"] == "tool-call"]
        said = texts[0] if texts else (f"Calling: {', '.join(calls)}" if calls else None)
        tool = ", ".join(c for c in calls if c) or None
    elif kind in ("tool_call", "tool_result"):
        tool = d.get("tool")
        args = d.get("args") if kind == "tool_call" else None
        said = d.get("result") if kind == "tool_result" else None
    elif kind == "delegate":
        tool, said = "ask_teammate", f"→ {d.get('to')}: {d.get('request')}"
    elif kind == "delegate_reply":
        said = f"← {d.get('from')}: {d.get('reply')}"
    elif kind == "finish":
        out = d.get("output", {})
        said = out.get("decision") or out.get("summary")
    elif kind in ("refused", "error"):
        said = d.get("reason") or d.get("error")
    elif kind == "model_request":
        said = "; ".join(f"{p['part']}{':' + p['tool'] if p.get('tool') else ''}" for p in d.get("parts", []))
    if isinstance(said, str) and len(said) > 600:
        said = said[:600] + "…"
    return {"at": e["at"], "run_id": e["run_id"], "step": e["step"], "agent": e["agent"],
            "depth": e["depth"], "chain": e.get("chain"), "ticket_id": e.get("ticket_id"),
            "kind": kind, "said": said, "tool": tool, "args": args}


@app.get("/api/events", summary="Recent agent events from output/audit_trail.json")
async def events(
    since: int | None = Query(None, ge=0, description="Return entries after this index (use `next` from the last call)."),
    limit: int = Query(100, ge=1, le=1000),
    ticket_id: int | None = None,
    run_id: str | None = None,
    include_model_requests: bool = Query(False, description="Also show what was sent to the model."),
):
    entries = _audit_entries()
    total = len(entries)
    indexed = list(enumerate(entries))
    if since is not None:
        indexed = indexed[since + 1:]
    if ticket_id is not None:
        indexed = [(i, e) for i, e in indexed if e.get("ticket_id") == ticket_id]
    if run_id is not None:
        indexed = [(i, e) for i, e in indexed if e.get("run_id") == run_id]
    if not include_model_requests:
        indexed = [(i, e) for i, e in indexed if e["kind"] != "model_request"]
    indexed = indexed[:limit] if since is not None else indexed[-limit:]
    return {
        "total": total,
        "next": indexed[-1][0] if indexed else (since if since is not None else total - 1),
        "events": [{"index": i, **_summarize(e)} for i, e in indexed],
    }


def _audit_entries() -> list[dict[str, Any]]:
    return json.loads(AUDIT_FILE.read_text()) if AUDIT_FILE.exists() and AUDIT_FILE.stat().st_size else []


@app.get("/api/tickets/{ticket_id}/summary", summary="What each agent did on the latest run of this ticket")
async def ticket_summary(ticket_id: int, run_id: str | None = None):
    entries = [e for e in _audit_entries() if e.get("ticket_id") == ticket_id]
    if not entries:
        return {"ticket_id": ticket_id, "run_id": None, "agents": []}
    run_id = run_id or entries[-1]["run_id"]
    entries = [e for e in entries if e["run_id"] == run_id]
    agents: dict[str, dict[str, Any]] = {}
    boss_decision = None
    for e in entries:
        a = agents.setdefault(e["agent"], {"agent": e["agent"], "asked_by": [], "runs": 0, "tools": {}, "delegated_to": [],
                                           "approval_ids": [], "board_ids": [], "summary": None,
                                           "tokens": 0, "steps": 0})
        a["steps"] += 1
        d = e.get("data", {})
        if e["kind"] == "start":
            a["runs"] += 1
            if len(e.get("chain", [])) > 1 and e["chain"][-2] not in a["asked_by"]:
                a["asked_by"].append(e["chain"][-2])
        elif e["kind"] == "tool_call":
            a["tools"][d["tool"]] = a["tools"].get(d["tool"], 0) + 1
        elif e["kind"] == "tool_result":
            try:
                res = json.loads(d.get("result") or "{}")
            except json.JSONDecodeError:
                res = {}
            if isinstance(res, dict) and res.get("approval_id"):
                a["approval_ids"].append(res["approval_id"])
            if isinstance(res, dict) and res.get("board_id"):
                a["board_ids"].append(res["board_id"])
        elif e["kind"] == "delegate":
            a["delegated_to"].append(d.get("to"))
        elif e["kind"] == "model_response":
            a["tokens"] += (d.get("input_tokens") or 0) + (d.get("output_tokens") or 0)
        elif e["kind"] == "finish":
            out = d.get("output", {})
            a["summary"] = out.get("decision") or out.get("summary")
            if e["agent"] == "boss" and e["depth"] == 0:
                boss_decision = out
        elif e["kind"] == "error":
            a["summary"] = f"Error: {d.get('error')}"
    order = ["boss", "inventory", "accounting", "facilities", "customer_service"]
    return {"ticket_id": ticket_id, "run_id": run_id, "started_at": entries[0]["at"], "last_at": entries[-1]["at"],
            "decision": boss_decision,
            "agents": sorted(agents.values(), key=lambda a: order.index(a["agent"]))}


# ------------------------------------------------------------------ 4. human approval

@app.get("/api/approvals", summary="Approval requests (filter by status, e.g. pending)")
async def approvals(status: str | None = None):
    return (await mcp("list_approvals", {"status": status} if status else {}))["approvals"]


@app.post("/api/approvals/{approval_id}/approve",
          summary="A human approves. Payments execute here: this is the only route that moves cash")
async def approve(approval_id: int, body: Decision):
    out = await shop_client.decide(approval_id, "approved", body.approver.strip(), body.note)
    if "error" in out["decision"]:
        raise HTTPException(409 if "already" in out["decision"]["error"] else 404, detail=out["decision"]["error"])
    executed = out.get("executed")
    if executed and "error" in executed:
        # Approved but could not execute (e.g. not enough cash, vendor still blocked). Nothing moved.
        raise HTTPException(409, detail={"approved": True, "executed": False, "reason": executed["error"]})
    out["ticket_resolved"] = await _settle_after_decision(approval_id, body.approver.strip())
    return out


async def _settle_after_decision(approval_id: int, approver: str) -> bool | None:
    approval = next((a for a in await approvals() if a["id"] == approval_id), None)
    if not approval or approval["ticket_id"] is None or _run_lock.locked():
        return None
    return await resolve_if_settled(approval["ticket_id"], by=approver)


@app.post("/api/approvals/{approval_id}/reject", summary="A human rejects a request. Nothing moves")
async def reject(approval_id: int, body: Decision):
    out = await shop_client.decide(approval_id, "rejected", body.approver.strip(), body.note)
    if "error" in out["decision"]:
        raise HTTPException(409 if "already" in out["decision"]["error"] else 404, detail=out["decision"]["error"])
    out["ticket_resolved"] = await _settle_after_decision(approval_id, body.approver.strip())
    return out


# ------------------------------------------------------------------ 5. cash

@app.get("/api/cash", summary="Current checking balance from cash_accounts")
async def cash():
    pos = await mcp("get_cash_position")
    checking = next((a for a in pos["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, detail="No 'checking' account in cash_accounts.")
    return {"account": "checking", "balance": checking["balance"], "as_of": checking["date"],
            "shop_date": pos["shop_date"], "accounts": pos["accounts"],
            "open_invoices_total": pos["open_invoices_total"], "rent_due_total": pos["rent_due_total"],
            "cash_after_commitments": pos["cash_after_commitments"]}


# ------------------------------------------------------------------ 6. reset

@app.post("/api/reset", summary="Reset the working database from the untouched original")
async def reset():
    if _run_lock.locked():
        raise HTTPException(409, detail="A team run is in progress; reset after it finishes.")
    out = await mcp("reset_working_db")
    return {**out, "note": "Working copy restored from campus_customs.db. The audit trail is kept (append-only)."}


# ------------------------------------------------------------------ extras for the board

@app.get("/api/board", summary="Drafts and notes on the board (never sent)")
async def board(ticket_id: int | None = None):
    return (await mcp("list_board", {"ticket_id": ticket_id} if ticket_id is not None else {}))["board"]


@app.get("/api/payments", summary="Payments made, with the human who approved each")
async def payments():
    return await mcp("list_payments")


@app.get("/api/health")
async def health():
    return {"ok": True, "model": MODEL_NAME, "running": _run_lock.locked()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=False)

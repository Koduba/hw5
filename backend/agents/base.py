"""Shared plumbing for all five agents: MCP tools, delegation, the audited agent loop.

Every agent:
- uses the one model from config.get_model() (gpt-6-luna via Portkey),
- reads its instructions from backend/prompts/<name>.md,
- sees only its own slice of the campus-customs MCP tools (never the human-only ones),
- can call ask_teammate() to delegate to ANY other agent (full connectivity),
  with depth and cycle guards so delegation always terminates,
- runs through run_agent(), which appends every loop step to output/audit_trail.json.
"""

import json
from typing import Any

from fastmcp import Client
from pydantic_ai import Agent, NativeOutput, RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset, ToolResult
from pydantic_ai.usage import RunUsage, UsageLimits

from .. import audit
from ..config import (MAX_DELEGATION_DEPTH, MODEL_NAME, PROMPT_DIR, REQUEST_LIMIT, mcp_client_config,
                      TOKEN_LIMIT, TOOL_CALLS_LIMIT, get_model)
from ..models import AGENT_NAMES, AgentName, BossDecision, SpecialistReport, TeamDeps, TraceEvent

# Tools on the MCP server that only a human (dashboard/CLI) may call.
HUMAN_ONLY_TOOLS = {"decide_approval", "reset_working_db"}

# Tool args that name who did something. We overwrite them with the real agent
# so an agent cannot file a request or post a draft under another name.
IDENTITY_ARGS = ("requested_by", "author")

AGENTS: dict[AgentName, Agent[TeamDeps, Any]] = {}


def usage_limits() -> UsageLimits:
    return UsageLimits(request_limit=REQUEST_LIMIT, tool_calls_limit=TOOL_CALLS_LIMIT,
                       total_tokens_limit=TOKEN_LIMIT)


def log(deps: TeamDeps, kind: str, data: dict[str, Any]) -> None:
    """Record one step in memory (for the API/dashboard) and append it to the audit file."""
    event = TraceEvent(run_id=deps.run_id, step=len(deps.trace) + 1, agent=deps.agent,
                       depth=deps.depth, chain=[*deps.chain, deps.agent], ticket_id=deps.ticket_id,
                       model=MODEL_NAME, kind=kind, data=audit.clip(data))
    deps.trace.append(event)
    audit.append(event.model_dump())


async def stamp_and_trace(ctx: RunContext[TeamDeps], call_tool: CallToolFunc,
                          name: str, args: dict[str, Any]) -> ToolResult:
    """Runs around every MCP tool call: block human-only tools, force true identity, audit."""
    if name in HUMAN_ONLY_TOOLS:  # belt and braces: these are never in an agent's slice anyway
        log(ctx.deps, "refused", {"tool": name, "args": args, "reason": "human-only tool"})
        return {"error": f"{name} is human-only. Ask a person to do it on the dashboard."}
    for key in IDENTITY_ARGS:
        if key in args:
            args[key] = ctx.deps.agent
    log(ctx.deps, "tool_call", {"tool": name, "args": args})
    result = await call_tool(name, args)
    log(ctx.deps, "tool_result", {"tool": name, "result": json.dumps(result, default=str)})
    return result


def _mcp_client() -> Client:
    return Client(mcp_client_config())


# One connection to the campus-customs MCP server, shared (ref-counted) by all agents.
SHOP_TOOLS = MCPToolset(_mcp_client(), id="campus-customs", process_tool_call=stamp_and_trace,
                        tool_error_behavior="retry", max_retries=2)


def _parts(parts) -> list[dict[str, Any]]:
    """Summarize message parts for the audit: who said what, which tool, with what."""
    out = []
    for p in parts:
        item: dict[str, Any] = {"part": p.part_kind}
        if getattr(p, "tool_name", None):
            item["tool"] = p.tool_name
        if p.part_kind == "tool-call":
            item["args"] = p.args if isinstance(p.args, (dict, str)) else str(p.args)
        elif p.part_kind == "thinking":
            item["content"] = "[reasoning omitted]"
        elif hasattr(p, "content"):
            item["content"] = p.content if isinstance(p.content, str) else json.dumps(p.content, default=str)
        out.append(item)
    return out


async def run_agent(name: AgentName, prompt: str, deps: TeamDeps, usage: RunUsage | None = None):
    """The agent loop, one audited step at a time.

    Each model request (what we sent: prompt, tool results, retries) and each
    model response (text, tool calls, tokens) is appended to the audit trail;
    tool calls/results are logged by stamp_and_trace; delegations by ask_teammate.
    """
    log(deps, "start", {"prompt": prompt})
    agent = AGENTS[name]
    try:
        async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=usage_limits()) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    log(deps, "model_request", {"parts": _parts(node.request.parts)})
                elif Agent.is_call_tools_node(node):
                    resp = node.model_response
                    log(deps, "model_response", {
                        "parts": _parts(resp.parts),
                        "model": resp.model_name,
                        "input_tokens": resp.usage.input_tokens,
                        "output_tokens": resp.usage.output_tokens,
                        "run_total_tokens": run.usage.total_tokens,
                    })
            result = run.result
    except Exception as exc:
        log(deps, "error", {"error": f"{type(exc).__name__}: {exc}"})
        raise
    log(deps, "finish", {"output": result.output.model_dump(), "requests": result.usage.requests,
                         "total_tokens": result.usage.total_tokens})
    return result


async def ask_teammate(ctx: RunContext[TeamDeps], teammate: AgentName, request: str) -> str:
    """Delegate work to another Campus Customs agent and get their report back.

    teammate: one of boss, inventory, accounting, facilities, customer_service.
    request: a complete, self-contained task — include the ticket number, SKUs,
    sizes, quantities, IDs and amounts they need. They cannot see your conversation.
    """
    me = ctx.deps.agent
    refusal = None
    if teammate == me:
        refusal = "Refused: you cannot delegate to yourself. Do the work with your own tools."
    elif teammate in ctx.deps.chain:
        path = " -> ".join([*ctx.deps.chain, me])
        refusal = (f"Refused: {teammate} is already waiting on you in this chain ({path}). "
                   "Answer with what you have; they will act on your report.")
    elif ctx.deps.depth >= MAX_DELEGATION_DEPTH:
        refusal = (f"Refused: delegation depth limit ({MAX_DELEGATION_DEPTH}) reached. "
                   "Use your own tools and report what is still unknown.")
    if refusal:
        log(ctx.deps, "refused", {"teammate": teammate, "request": request, "reason": refusal})
        return refusal
    log(ctx.deps, "delegate", {"to": teammate, "request": request})
    try:
        result = await run_agent(teammate, request, ctx.deps.child(teammate), usage=ctx.usage)
    except Exception as exc:  # report the failure to the caller instead of crashing the team
        return f"{teammate} could not finish: {type(exc).__name__}: {exc}"
    reply = result.output.model_dump_json()
    log(ctx.deps, "delegate_reply", {"from": teammate, "reply": reply})
    return reply


def _runtime_context(ctx: RunContext[TeamDeps]) -> str:
    d = ctx.deps
    caller = d.chain[-1] if d.chain else "the human operator (dashboard or chat)"
    left = MAX_DELEGATION_DEPTH - d.depth
    return (
        f"## This run\n"
        f"- You are: {d.agent}\n"
        f"- You were asked by: {caller}\n"
        f"- Delegation chain so far: {' -> '.join([*d.chain, d.agent])}\n"
        f"- Ticket in focus: {d.ticket_id if d.ticket_id is not None else 'none given'}\n"
        f"- Delegation hops left: {left}. "
        + ("You may still use ask_teammate." if left > 0 else "You cannot delegate further; use your own tools.")
        + "\n- Budget: the whole team shares a limited number of model calls and tokens for this run. "
          "Don't repeat a tool call whose answer you already have, and delegate only when you need that teammate's expertise."
    )


def build_agent(name: AgentName, tool_names: set[str]) -> Agent[TeamDeps, Any]:
    """Create one team member with its prompt file, its tool slice and the delegation tool."""
    assert name in AGENT_NAMES
    leaked = tool_names & HUMAN_ONLY_TOOLS
    if leaked:
        raise RuntimeError(f"{name} must not get human-only tools: {sorted(leaked)}")
    prompt = (PROMPT_DIR / f"{name}.md").read_text()
    agent = Agent(
        get_model(),
        name=name,
        deps_type=TeamDeps,
        # Native JSON-schema output, not an output tool: forcing tool_choice="required" makes
        # gpt-6-luna stall through Portkey after a long tool reply (seen after delegation).
        output_type=NativeOutput(BossDecision if name == "boss" else SpecialistReport),
        instructions=[prompt, _runtime_context],
        toolsets=[SHOP_TOOLS.filtered(lambda ctx, tool_def: tool_def.name in tool_names)],
        tools=[ask_teammate],
        retries=2,
    )
    AGENTS[name] = agent
    return agent

"""Agent loop entry points: work a ticket through the boss, or talk to any agent directly."""

import uuid

from .agents import SHOP_TOOLS
from .agents.base import run_agent
from .models import AgentName, TeamDeps, TeamRunResult


async def ask(agent: AgentName, message: str, ticket_id: int | None = None,
              run_id: str | None = None) -> TeamRunResult:
    """Send your own words to one agent. It may delegate to any teammate before answering.
    Every step is appended to output/audit_trail.json as it happens."""
    deps = TeamDeps(agent=agent, run_id=run_id or uuid.uuid4().hex[:8], ticket_id=ticket_id)
    async with SHOP_TOOLS:  # one MCP connection for the whole team run
        result = await run_agent(agent, message, deps)
    usage = result.usage
    return TeamRunResult(run_id=deps.run_id, agent=agent, prompt=message, output=result.output,
                         trace=deps.trace, requests=usage.requests, total_tokens=usage.total_tokens)


async def run_ticket(ticket_id: int, run_id: str | None = None) -> TeamRunResult:
    """The main loop for one ticket: the boss reads it, delegates, and makes the final call."""
    prompt = (f"Work ticket {ticket_id} from start to finish. Read it with get_ticket, delegate to "
              "the right teammates, file any approvals a human must make, make sure the right drafts "
              "are on the board, set the ticket status, and give your final decision.")
    return await ask("boss", prompt, ticket_id=ticket_id, run_id=run_id)

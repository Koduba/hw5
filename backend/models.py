"""Data types shared by the Campus Customs agent team."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

TicketStatus = Literal["open", "in_progress", "waiting_on_human", "resolved"]


class TraceEvent(BaseModel):
    """One agent loop step. Appended to output/audit_trail.json as it happens and shown on the dashboard."""

    at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    run_id: str
    step: int = Field(description="Order of this step within the team run (shared across delegations).")
    agent: AgentName
    depth: int
    chain: list[AgentName] = Field(description="Who called whom to reach this agent.")
    ticket_id: int | None = None
    model: str
    kind: Literal["start", "model_request", "model_response", "tool_call", "tool_result",
                  "delegate", "delegate_reply", "refused", "finish", "error"]
    data: dict[str, Any] = Field(default_factory=dict, description="What was sent/returned, enough to audit.")


@dataclass
class TeamDeps:
    """Per-run context. Each delegated run gets a child copy with its own agent/depth/chain."""

    agent: AgentName
    run_id: str
    ticket_id: int | None = None
    depth: int = 0
    chain: list[AgentName] = field(default_factory=list)  # who called whom to get here
    trace: list[TraceEvent] = field(default_factory=list)  # shared across the whole team run

    def child(self, agent: AgentName) -> "TeamDeps":
        return TeamDeps(agent=agent, run_id=self.run_id, ticket_id=self.ticket_id,
                        depth=self.depth + 1, chain=[*self.chain, self.agent], trace=self.trace)


class SpecialistReport(BaseModel):
    """What inventory, accounting, facilities and customer service hand back."""

    agent: AgentName
    ticket_id: int | None = Field(None, description="Ticket this work is for, if any.")
    summary: str = Field(description="Two or three sentences: the answer to what you were asked.")
    facts: list[str] = Field(
        default_factory=list,
        description="Numbers and rows you relied on, each with its source table, e.g. 'inventory: CC-TEE-WHITE S qty 0'.",
    )
    actions_taken: list[str] = Field(default_factory=list, description="Tool calls that changed anything.")
    approval_ids: list[int] = Field(default_factory=list, description="Approval requests you filed for a human.")
    board_ids: list[int] = Field(default_factory=list, description="Drafts or notes you posted to the board.")
    blockers: list[str] = Field(default_factory=list, description="What stops this from being finished.")
    needs_human: bool = Field(description="True if a person must approve or decide something before work can finish.")
    recommendation: str = Field(description="What you recommend the boss decide next.")


class BossDecision(BaseModel):
    """The boss's final call on a ticket (or on a question asked directly)."""

    ticket_id: int | None = None
    assigned_to: list[AgentName] = Field(default_factory=list, description="Teammates who worked on it.")
    decision: str = Field(description="The final call in plain words, with the key numbers.")
    reasons: list[str] = Field(default_factory=list, description="Why, citing the shop rules and data.")
    final_status: TicketStatus | None = Field(None, description="Status you set on the ticket.")
    approval_ids: list[int] = Field(default_factory=list, description="Approvals waiting on a human.")
    board_ids: list[int] = Field(default_factory=list, description="Drafts/notes on the board for this ticket.")
    human_actions_needed: list[str] = Field(default_factory=list, description="Exactly what a person must do next.")


class TeamRunResult(BaseModel):
    """Returned by run_ticket / ask: the output plus the full trace for the dashboard."""

    run_id: str
    agent: AgentName
    prompt: str
    output: BossDecision | SpecialistReport
    trace: list[TraceEvent]
    requests: int
    total_tokens: int

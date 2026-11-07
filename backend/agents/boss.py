"""Boss: reads each ticket, routes it, makes the final call, sets ticket status."""

from .base import build_agent

TOOLS = {
    "list_open_tickets", "get_ticket", "get_cash_position", "list_approvals",
    "list_board", "update_ticket", "post_draft", "list_tickets", "list_payments",
}

boss = build_agent("boss", TOOLS)

"""Facilities: the shop space, lease terms, rent due dates, landlord drafts."""

from .base import build_agent

TOOLS = {
    "get_ticket", "get_lease", "get_cash_position", "post_draft", "list_payments", "list_approvals", "list_board",
}

facilities = build_agent("facilities", TOOLS)

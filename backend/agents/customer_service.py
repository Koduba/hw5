"""Customer service: drafts messages to customers. Drafts stay on the board; nothing is sent."""

from .base import build_agent

TOOLS = {
    "get_ticket", "check_stock", "post_draft", "list_approvals", "list_board",
}

customer_service = build_agent("customer_service", TOOLS)

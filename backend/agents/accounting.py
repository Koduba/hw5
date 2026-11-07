"""Accounting: cash, invoices, margins, discount pricing, payment requests (human approves)."""

from .base import build_agent

TOOLS = {
    "get_ticket", "get_cash_position", "list_open_invoices", "get_vendor_status", "list_vendors",
    "get_lease", "check_stock", "check_margin", "request_payment", "request_discount",
    "pay_approved_request", "list_payments", "list_approvals", "list_board",
}

accounting = build_agent("accounting", TOOLS)

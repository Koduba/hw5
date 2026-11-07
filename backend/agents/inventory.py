"""Inventory: stock by SKU and size, shortfalls, which vendor can restock, purchase orders."""

from .base import build_agent

TOOLS = {
    "get_ticket", "check_stock", "list_inventory", "list_out_of_stock", "get_vendor_status", "list_vendors",
    "request_purchase_order", "place_approved_purchase_order", "list_approvals", "list_board",
}

inventory = build_agent("inventory", TOOLS)

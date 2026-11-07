"""Campus Customs MCP server — the one and only path to shop data.

Talks only to data/campus_customs_new.db (the working copy). Run with:
    python mcp_server/server.py

Agents can READ and can REQUEST payments, purchase orders and discounts.
Approving and resetting are HUMAN_ONLY tools: they live on this server so the
dashboard/CLI also goes through MCP, but no agent's tool slice includes them
(backend/agents/base.py refuses to build an agent that has one).
"""

from fastmcp import FastMCP

import db_tools as db

mcp = FastMCP("campus-customs")

AGENT_TOOLS = [
    # read
    db.list_open_tickets,
    db.list_tickets,
    db.get_ticket,
    db.check_stock,
    db.list_inventory,
    db.list_out_of_stock,
    db.get_vendor_status,
    db.list_vendors,
    db.list_open_invoices,
    db.get_lease,
    db.get_cash_position,
    db.check_margin,
    db.list_payments,
    db.list_approvals,
    db.list_board,
    # request (a human must approve)
    db.request_payment,
    db.request_purchase_order,
    db.request_discount,
    # execute (refuses unless a human already approved)
    db.pay_approved_request,
    db.place_approved_purchase_order,
    # board and tickets
    db.post_draft,
    db.update_ticket,
]

HUMAN_ONLY_TOOLS = [
    db.decide_approval,
    db.reset_working_db,
]

for fn in AGENT_TOOLS:
    mcp.tool(fn, tags={"agent"})
for fn in HUMAN_ONLY_TOOLS:
    mcp.tool(fn, tags={"human_only"})

if __name__ == "__main__":
    mcp.run(show_banner=False)

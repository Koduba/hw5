# Campus Customs MCP Server

A FastMCP server that holds the shared toolbox for the Campus Customs agent team. Every agent (boss, inventory, accounting, facilities, customer service) reads and updates the shop through these tools instead of opening the database itself.

## Database

- It uses **`data/campus_customs_new.db`**, the working copy.
- `data/campus_customs.db` is the original. It is never modified, and the server refuses to open it, so the working copy can always be reset from it.
- You can point it at another working copy with the `CAMPUS_DB_PATH` environment variable (it never opens the original).
- "Today" is `desk.date_today` in the database, not the system clock.

## Tools (24)

This server is the only path to shop data. The agents (through `MCPToolset`) and the human CLI/dashboard (through `backend/shop_client.py`) both call it. Nothing else opens the database.

| Group | Tools |
|---|---|
| Read | `list_open_tickets`, `list_tickets`, `get_ticket`, `check_stock`, `list_inventory`, `list_out_of_stock`, `get_vendor_status`, `list_vendors`, `list_open_invoices`, `get_lease`, `get_cash_position`, `check_margin`, `list_payments`, `list_approvals`, `list_board` |
| Request (a human must approve) | `request_payment`, `request_purchase_order`, `request_discount` |
| Execute (refuses without human approval) | `pay_approved_request` (also refuses if cash would go negative), `place_approved_purchase_order` (also refuses while the vendor has an open invoice) |
| Board and tickets | `post_draft` (drafts only, never sent), `update_ticket` (can't resolve a ticket with a pending approval) |
| **Human-only** (tag `human_only`, given to no agent) | `decide_approval`, `reset_working_db` |

- **Agent tools** are tagged `agent`. `backend/agents/base.py` refuses to build an agent whose tool slice includes a human-only tool, and it also blocks such a call at runtime.
- **Operating tables:** `approvals` and `board` are created in the working copy on its first write.
- **No made-up data:** every tool returns data from the database only, and an unknown ID gives an error.
- **Human commands,** run from the repo root:
  - `.venv/bin/python -m backend.chat --approvals`
  - `--approve ID --by "Name"`
  - `--reject ID --by "Name"`
  - `--reset`

## Run

From the repo root, after `pip install -r requirements.txt` into `.venv`:

```bash
.venv/bin/python mcp_server/server.py
```

It speaks MCP over stdio. You normally don't start it by hand: the backend and the coding agent launch it from `.mcp.json`.

## Connect from the vibe coder

`.mcp.json` at the repo root registers this server as `campus-customs`. The command is `.venv/bin/python mcp_server/server.py`, with paths relative to the repo root, so there are no machine-specific paths. Open Claude Code at the repo root and approve the project MCP server when it asks; the agent can then call the tools directly. Run `.venv/bin/python mcp_server/smoke_test.py` to check every tool against the database.

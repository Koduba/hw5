# Campus Customs: Multi-Agent Ops Desk (HW5)

An agent team that runs a small campus apparel shop.

- **Agents:** five Pydantic AI agents (boss, inventory, accounting, facilities, customer service) on `gpt-6-luna` through Portkey. Any agent can delegate to any other.
- **MCP server:** every shop fact and change goes through one FastMCP server over a SQLite working copy.
- **Backend:** FastAPI runs the team and records human approvals.
- **Dashboard:** a React board where a person watches the agents and approves every payment.

```
React board (:5173) → FastAPI backend (:8000) → 5 agents → MCP server → data/campus_customs_new.db
```

## Layout

```
hw5/
├── AI_prompts.md            prompts used to build this, per problem
├── requirements.txt         one Python environment for the MCP server, agents and backend
├── .env.example             variable names only (copy to .env)
├── .gitignore
├── .mcp.json                registers the MCP server (repo-relative paths)
├── README.md
├── data/
│   ├── campus_customs.db        original shop database (never modified)
│   └── campus_customs_new.db    working copy the tools read and write
├── mcp_server/
│   ├── server.py                FastMCP server (24 tools)
│   ├── README.md
│   ├── db_tools.py              the SQL behind each tool
│   └── smoke_test.py            checks each tool's output against the DB
├── frontend/                React + Vite + TypeScript board
├── backend/
│   ├── main.py                  FastAPI routes
│   ├── models.py                data types
│   ├── prompts/                 boss.md, inventory.md, accounting.md, facilities.md, customer_service.md
│   ├── agents/                  the five agents plus the shared loop (base.py)
│   └── config.py, team.py, chat.py, audit.py, shop_client.py
└── output/
    ├── harness.md               reference: tables, MCP tools, agents, routes, dashboard, safety
    ├── mcp_smoke.json           MCP tool evidence
    ├── desk_tickets.html        expected vs actual per ticket, the cash breakdown, and the reflection
    ├── design.md                dashboard design rationale
    ├── resolved_tickets.json    per-ticket results
    ├── resolved_board.html      screenshots of the board for tickets 101, 102 and 103
    ├── audit_trail.json         append-only trail of every agent step
    └── github_url.txt
```

## Setup (once)

You need Python 3.12 and Node 20+. Run these from the repo root.

1. Create the Python environment and install the packages:
   ```bash
   python3.12 -m venv .venv
   ```
   ```bash
   .venv/bin/pip install -r requirements.txt
   ```
2. Copy the example settings file:
   ```bash
   cp .env.example .env
   ```
   Then put your Portkey key in `.env` as `PORTKEY_API_KEY`. Every agent uses `gpt-6-luna` through Portkey, and the backend refuses any other model.
3. Install the dashboard's packages:
   ```bash
   cd frontend && npm install
   ```

## 1. Get a clean working database

The tools only ever touch `data/campus_customs_new.db`, and `data/campus_customs.db` stays untouched as the original. For a clean run, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

This resets cash to $3,400.00, reopens all three tickets, and clears approvals, payments and drafts. `.venv/bin/python -m backend.chat --reset` does the same thing through the MCP server.

## 2. Start the MCP server

The MCP server is `mcp_server/server.py`. It talks MCP over stdio, so the program that uses it starts it from `.mcp.json`:
- **The backend** starts it automatically when it boots.
- **A coding agent** (Claude Code) starts it when opened at the repo root; approve the `campus-customs` server when asked.

To run it by hand, or to check its tools:

```bash
.venv/bin/python mcp_server/server.py
```
```bash
.venv/bin/python mcp_server/smoke_test.py
```

The smoke test checks every tool's answer against the database and writes the result to `output/mcp_smoke.json`.

## 3. Start the FastAPI backend

```bash
cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000
```

It serves http://localhost:8000, with route docs at `/docs`. It allows the board's origin (`http://localhost:5173`) through CORS. All routes are listed in `output/harness.md` §6.

## 4. Start the React board

In a second terminal:

```bash
cd frontend && npm run dev
```

It opens http://localhost:5173.

## 5. Full three-ticket run

1. **Reset the database first.** Click **Reset shop** on the board, or call `POST /api/reset`, or run the `cp` command from step 1. Checking should read **$3,400.00**, and tickets 101, 102 and 103 should be **Open**.
2. **Type your name in On desk** (top right). It's recorded as the approver on every decision.
3. **Run the tickets.** Pick ticket **101**, click **Run the agent team**, and watch the agent floor. Then do the same for **102** and **103**.
4. **Decide the requests** in **Needs your OK**: **Approve & pay**, **Approve & place PO**, or **Reject**. Payments only move cash after your click. A ticket the boss left for a person shows **Mark resolved**.
5. **Check the result.** When all three are resolved, checking should be **$160.00** ($3,400 − $840 invoice − $2,400 rent). That's the same as `cash_accounts` in the working database.

## Result of our run

All three tickets were resolved, and checking went **$3,400.00 → $160.00**. A person approved both payments on the board. See `output/desk_tickets.html` (the Cash tab), `output/resolved_tickets.json`, and `output/resolved_board.html`.

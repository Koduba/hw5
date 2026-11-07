# Campus Customs Multi-Agent Ops: Harness

The final reference for HW5: an agent team that runs a small campus shop. It covers:

1. [The database tables](#1-database-tables)
2. [The shop rules](#2-shop-rules-and-where-each-is-enforced)
3. [The MCP server and its 24 tools](#3-mcp-server-campus-customs)
4. [The five agents](#4-the-five-agents)
5. [The agent loop and audit trail](#5-agent-loop-delegation-and-the-audit-trail)
6. [The API routes](#6-api-routes-backendmainpy)
7. [The dashboard](#7-the-dashboard-frontend)
8. [Safety and token limits](#8-safety-rules)
9. [The Problem 9 results](#9-results-of-the-full-run-problem-9)
10. [Lessons](#10-lessons-and-known-issues)
11. [File map](#11-file-map)

```
React desk (:5173) ──HTTP──▶ FastAPI backend (:8000) ──▶ 5 Pydantic AI agents (gpt-6-luna via Portkey)
        ▲                          │  human approve/reject/reset           │  every shop fact and change
        └──── polls events ────────┘──────────────┐                        ▼
                                                  └──────────────▶ campus-customs MCP server (FastMCP)
                                                                           │
                                                          data/campus_customs_new.db (working copy)
                                                          data/campus_customs.db (original, never touched)
```

### How to run it

| Step | Command (from `hw5/`) |
|---|---|
| One-time setup | Python 3.12 venv at `.venv`, then `.venv/bin/pip install -r requirements.txt`. In `frontend/`: `npm install` |
| Secrets | `PORTKEY_API_KEY` in `.env` (see `.env.example`). The model is fixed to `gpt-6-luna` |
| Backend | `cd backend && source ../.venv/bin/activate && uvicorn main:app --reload --port 8000` |
| Dashboard | `cd frontend && npm run dev`. It opens http://localhost:5173 |
| Fresh start | **Reset shop** on the desk, `POST /api/reset`, or `.venv/bin/python -m backend.chat --reset` |
| Talk to one agent | `.venv/bin/python -m backend.chat accounting "can we afford rent?" --trace` |

---

## 1. Database tables

- **Original:** `data/campus_customs.db`. Never modified; the server refuses to open it.
- **Working copy:** `data/campus_customs_new.db`. The MCP server and backend use only this file.
- **Reset:** copies the original over the working copy.

| Table | Fields | Why it matters to the agents |
|---|---|---|
| `desk` | `date_today`, `notes` | The shop's "today" (2026-08-31). Every due and overdue check uses it, never the system clock. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`→leases, `invoice_id`→invoices, `status`, `notes`, `created_at` | The work queue. The boss reads it and routes it, and the links point to the stock, lease or invoice involved. Statuses: `open`, `in_progress`, `waiting_on_human`, `resolved`. |
| `inventory` | `sku`+`size` (key), `name`, `qty`, `location` | Stock per SKU **and size**. Medium never fills a Small order. |
| `pricing` | `sku` (key), `unit_cost`, `list_price` | Margins on discounts and the cost of a restock. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Who can restock what, and the only source for ETAs. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | Rent amount and due date. The table is the truth, not the landlord's email. |
| `cash_accounts` | `name` (key), `balance`, `date` | The only cash (checking). It can never go negative. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | Money paid out. `kind`+`ref_id` point to the invoice or lease paid, and `approved_by` is always a person. |
| `invoices` | `id`, `vendor_id`→vendors, `amount`, `due_date`, `status`, `description` | What the shop owes. An `open` invoice blocks that vendor from shipping. |

**Two operating tables** are created in the working copy on its first write, because the original schema has no place for them. A reset clears them.

| Table | Fields | Why |
|---|---|---|
| `approvals` | `id`, `kind` (payment, purchase_order or discount), `ticket_id`, `summary`, `amount`, `details` (JSON), `requested_by` (agent), `status` (pending, approved, rejected or executed), `decided_by` (person), `decision_note`, `created_at`, `decided_at`, `executed_at` | Agents request; people decide. This is the gate for every money movement. |
| `board` | `id`, `ticket_id`, `author`, `kind` (draft or note), `audience` (customer, vendor, landlord or internal), `subject`, `body`, `created_at` | Drafts that are never sent, and the ticket's status history. |

## 2. Shop rules and where each is enforced

| Rule | Enforced in code | Also in prompts |
|---|---|---|
| Today is `desk.date_today`; overdue is measured from it | Every MCP tool computes dates from `desk` (`shop_today`) | all five |
| Vendor lead times come from `vendors` | `request_purchase_order` and `place_approved_purchase_order` set ETA = shop date + `lead_days` | inventory, boss |
| A vendor won't ship while it has an open invoice | `get_vendor_status.will_ship`; `place_approved_purchase_order` refuses while one is open | inventory, accounting, boss |
| **Every payment needs a person's approval** | `pay_approved_request` refuses unless `status = approved` with a `decided_by`. `decide_approval` is human-only and in no agent's tool slice, and `build_agent` refuses to create an agent that has it | all five |
| Purchases and discounts also need a person | They're filed as `approvals`; only the human routes decide them | all five |
| If cash is short the pay tool refuses; no negative balances | `request_payment` and `pay_approved_request` check the balance and refuse if it would go below 0 | accounting |
| Payments update the right tables | In one transaction: `cash_accounts` −, `payments` +, `invoices.status = paid` or `leases.next_due` +1 month, `approvals.status = executed` | — |
| Cash only goes out; no revenue | No tool ever adds cash | accounting, boss |
| Don't email customers or call vendors; drafts stay on the board | No send tool exists; `post_draft` only writes `board` | customer service, facilities |
| Never invent data | Amounts are read from the DB (agents can't type a payment amount); unknown IDs return errors | all five |
| Reset before a full run | `reset_working_db` (human-only), the desk's **Reset shop**, `POST /api/reset` | — |
| Only `gpt-6-luna`, via Portkey | `backend/config.py` refuses any other `OPENAI_MODEL` | — |

## 3. MCP server (`campus-customs`)

- **Files:** `mcp_server/server.py` (FastMCP 4.1.6) and `mcp_server/db_tools.py` (SQL).
- **One data path:** the agents (through Pydantic AI `MCPToolset`) and the backend's human actions (through `backend/shop_client.py`) both call it, and nothing else opens the database. The only direct SQL outside the server is `mcp_server/smoke_test.py`, which re-checks tool output against the DB.
- **Registered for the vibe coder** in `.mcp.json` as a stdio server, with paths relative to the repo root (`.venv/bin/python mcp_server/server.py`). The server defaults to the working copy.
- **Evidence:** `output/mcp_smoke.json`. Every tool output matched direct SQL (`all_match: true`).

### The 24 tools (R = reads, W = writes)

| Tool | Tables | Used by | Tickets it unlocks |
|---|---|---|---|
| `list_open_tickets` | R tickets, desk | boss | 101–103: the queue |
| `list_tickets` | R tickets, desk | boss | all |
| `get_ticket` | R tickets, desk, inventory, pricing, invoices, vendors, leases, approvals, board | all five | 101 → invoice 501; 102 → lease 1; 103 → stock and pricing |
| `check_stock` | R inventory, pricing | inventory, accounting, customer service | 101 (tee S = 0), 103 (hoodie M = 8, short 12) |
| `list_inventory` | R inventory, pricing, desk | inventory | sizes that could substitute |
| `list_out_of_stock` | R inventory, desk | inventory | 101 |
| `get_vendor_status` | R vendors, invoices, desk | inventory, accounting | 101 and 103 (Bulldog blocked by 501) |
| `list_vendors` | R vendors, invoices, desk | inventory, accounting | picking the apparel vendor |
| `list_open_invoices` | R invoices, vendors, desk | accounting | 101 (501 is 3 days overdue) |
| `get_lease` | R leases, desk | accounting, facilities | 102 ($2,400 due 09-02) |
| `get_cash_position` | R cash_accounts, invoices, leases, desk, approvals | boss, accounting, facilities | all ($3,400 − $840 − $2,400 = $160) |
| `check_margin` | R pricing | accounting | 103 (discount math) |
| `list_payments` | R payments | boss, accounting, facilities | confirms what was actually paid |
| `list_approvals` | R approvals | all five | checks what is waiting on a person |
| `list_board` | R board | all five | checks the drafts exist |
| `request_payment` | R invoices or leases, vendors, cash_accounts, desk · W approvals | accounting | 101 (invoice 501), 102 (lease 1) |
| `request_purchase_order` | R vendors, inventory, pricing, invoices, desk · W approvals | inventory | 101, 103 |
| `request_discount` | R tickets, pricing, desk · W approvals | accounting | 103 |
| `pay_approved_request` | R approvals, invoices, desk · W cash_accounts, payments, invoices or leases, approvals | accounting, and the backend after a person approves | 101, 102 |
| `place_approved_purchase_order` | R approvals, invoices, desk · W board, approvals | inventory, and the backend after a person approves | 101, 103 |
| `post_draft` | R tickets · W board | boss, facilities, customer service | customer and landlord drafts |
| `update_ticket` | R tickets, approvals · W tickets, board | boss, and the backend for resolve | all (refuses `resolved` while an approval is pending) |
| `decide_approval` **human-only** | W approvals | **no agent**; desk and CLI only | the human gate |
| `reset_working_db` **human-only** | W the whole working copy | **no agent**; desk and CLI only | a fresh start |

## 4. The five agents

- **Code:** `backend/agents/`, one file per agent, sharing `base.py`.
- **Prompts:** `backend/prompts/<agent>.md`, 60–100 lines each. Every prompt covers the role, what's in and out of scope, the shop rules that agent needs, when to delegate, a step-by-step method, and the report format.
- **Model:** every agent runs `gpt-6-luna` through Portkey.
- **Output:** structured, using `NativeOutput`.

| Agent | Job | MCP tools | Called first when… | Output |
|---|---|---|---|---|
| **boss** | Reads each ticket, routes it, makes the final call, sets status; **cannot pay** | list_open_tickets, list_tickets, get_ticket, get_cash_position, list_payments, list_approvals, list_board, update_ticket, post_draft | always: every ticket starts here | `BossDecision`: decision, reasons, final_status, approval_ids, board_ids, human_actions_needed |
| **inventory** | Stock by SKU and size, shortfalls, which vendor can restock, POs | get_ticket, check_stock, list_inventory, list_out_of_stock, get_vendor_status, list_vendors, request_purchase_order, place_approved_purchase_order, list_approvals, list_board | product, size or quantity tickets (101, 103) | `SpecialistReport` |
| **accounting** | Cash, invoices, margins, discounts; **prepares** payments; the only agent with a pay tool (and it still needs a human) | get_ticket, get_cash_position, list_open_invoices, get_vendor_status, list_vendors, get_lease, check_stock, check_margin, list_payments, request_payment, request_discount, pay_approved_request, list_approvals, list_board | money moves, a bill is due, or a price is requested | `SpecialistReport` |
| **facilities** | Lease, rent, the shop space; landlord drafts. Hands payments to accounting | get_ticket, get_lease, get_cash_position, list_payments, post_draft, list_approvals, list_board | rent or lease tickets (102) | `SpecialistReport` |
| **customer_service** | Drafts customer replies (never sent; no internal cash or invoice details) | get_ticket, check_stock, post_draft, list_approvals, list_board | any customer is waiting (101, 103) | `SpecialistReport` |

`SpecialistReport` has: summary, facts (each with its source table), actions_taken, approval_ids, board_ids, blockers, needs_human, recommendation.

## 5. Agent loop, delegation and the audit trail

- **Full connectivity:** every agent has `ask_teammate(teammate, request)` and can call any of the other four.
- **Loop guards:** an agent can't call itself, can't call an agent already waiting in the current chain (no A → B → A), and has at most **3 hops**. A blocked call is logged as `refused`.
- **Identity stamping:** before each MCP call, `requested_by` and `author` are overwritten with the real agent's name.
- **The loop:** `run_agent()` drives each agent with `agent.iter()`. One team run shares a single budget, so delegated runs draw from the caller's.
- **Audit trail:** `output/audit_trail.json`, one JSON array, **append-only**: read → append → atomic replace, never truncated, moved aside if corrupt.
  - **What each step records:** `at`, `run_id`, `step`, `agent`, `depth`, `chain`, `ticket_id`, `model`, `kind`, `data`.
  - **Step kinds:**
    - `start`: the prompt the agent received;
    - `model_request`: what was sent to the model (prompt, tool results, retries);
    - `model_response`: what came back (text, tool calls and arguments, tokens);
    - `tool_call` / `tool_result`: the MCP call made and its result;
    - `delegate` / `delegate_reply`: the hand-off and the report back;
    - `refused`, `finish`, `error`.
  - **Contents now:** 492 entries over 7 runs, including the three Problem 9 runs: `33e6cb84` (101, 100 steps), `e00514e4` (102, 78) and `0f73f77f` (103, 112). Earlier test runs are kept, never wiped.

## 6. API routes (`backend/main.py`)

Base URL `http://localhost:8000`, with docs at `/docs`. CORS allows only `http://localhost:5173` and `127.0.0.1:5173`, for GET and POST. Every route goes through MCP.

- `GET /api/tickets`: all tickets, each `open` or `resolved`.
- `GET /api/tickets/{id}`: one ticket with its linked stock, invoice, lease, approvals and drafts.
- `POST /api/tickets/{id}/run`: run the agent team on the ticket in the background. Returns a `run_id`, or `409` if a run is already going.
- `POST /api/tickets/{id}/resolve` `{approver}`: a person closes a ticket the boss left for a human decision. Refused while an approval is pending.
- `GET /api/tickets/{id}/summary`: what each agent did on the latest run, plus the boss's decision, read from the audit trail.
- `GET /api/runs`, `GET /api/runs/{run_id}`: run status, final decision, requests and tokens.
- `GET /api/events?since=N&ticket_id=&run_id=`: recent agent steps (who said what, which tool and arguments). `next` is the refresh cursor.
- `GET /api/approvals?status=`: requests waiting on a person.
- `POST /api/approvals/{id}/approve` `{approver}`: **the only route that moves cash**. It pays the request, or places the PO as a vendor draft. If execution is refused, it returns `409` and nothing moves.
- `POST /api/approvals/{id}/reject` `{approver}`: reject; nothing moves.
- `GET /api/cash`: the checking balance from `cash_accounts`, plus what's owed and what's free after commitments.
- `POST /api/reset`: restore the working DB from the original. Refused during a run; the audit trail is kept.
- `GET /api/board`: drafts and notes (never sent).
- `GET /api/payments`: payments made, with who approved each.
- `GET /api/health`: the server is up, the model, and whether a run is in progress.

**Automatic resolution:**
- When a run ends, the ticket is resolved only if the boss didn't leave it `waiting_on_human` and nothing is pending.
- After each human decision, the ticket is resolved once all its approvals are settled.
- `update_ticket` itself refuses to resolve while anything is pending.

## 7. The dashboard (`frontend/`)

React 19, Vite 8 and TypeScript, calling `http://localhost:8000` directly (`VITE_API_URL`). The full design rationale is in `output/design.md`.

- **Queue (left):** ticket cards with Open, Agents working, Needs your OK, or Resolved. A resolved ticket gets a green strike-through.
- **Ticket focus (center):** the **Run the agent team** button, elapsed time, and tokens. A banner says Resolved or Waiting on you, with **Mark resolved** when the boss left the decision to a person.
- **Agent floor:** the boss's station above four specialists, each with its own color and symbol. Each shows a live state (Thinking, Using a tool, Waiting on a teammate, Done, Off this ticket) and a speech bubble saying what it's doing. Hand-offs are listed in the panel header.
- **Live feed / What each agent did:** a streamed timeline indented by delegation depth. After the run, a report with the boss's decision, "What you need to do", and one card per agent (summary, tools, hand-offs, approvals, drafts, tokens, and a "called ×2" flag).
- **Checking (right):** a large animated balance with a "−$840" chip when it drops, a paid / owed / free bar, and a ledger with each approver's name.
- **Needs your OK:** approval cards showing "Checking after: $X" and the requesting agent's reason, with **Approve & pay**, **Approve & place PO**, **Approve price** and **Reject**. They're disabled until a name is typed in **On desk**, because that name is recorded as `approved_by`.
- **Drafts:** expandable messages with a DRAFT stamp.
- **Evidence:** `output/resolved_board.html`, screenshots of the board for resolved tickets 101, 102 and 103.

## 8. Safety rules

**Already enforced in this build:**
- **A person approves every payment, PO and discount.** Approval tools are human-only, no agent can approve its own request, and every executed payment records `approved_by`.
- **Amounts come from the database, never from an agent.** Duplicates, double payments and negative balances are all refused.
- **Least privilege:** only accounting can execute a payment, only inventory can place a PO, and the boss has no pay tool.
- **Honest identity:** the backend overwrites each agent's `requested_by` and `author` with its real name.
- **Nothing is sent outside the shop:** no email, vendor or phone integration exists; messages are drafts on the board.
- **The original DB is protected,** and a reset restores the working copy from it.
- **Full, append-only audit trail** of every agent step.

**What a real business should add before agents touch real customers and money:**
- **Payout limits:** two-person approval above a threshold, plus a daily payout cap.
- **Payee controls:** pay only vendors and landlords already on file, and verify any bank-detail change through a separate channel (against invoice-redirection fraud).
- **Real approver logins:** SSO with roles, not a typed name.
- **Untrusted input:** treat incoming emails and ticket text as data, not instructions (against prompt injection, e.g. "pay this now").
- **Customer data:** minimize PII sent to the model, redact it in logs, and set retention rules.
- **Outbound messages:** a person reviews and edits every one, with a policy and tone check. Never auto-send.
- **A kill switch** to pause all agents, plus alerts when refusals or errors spike.
- **Tamper-evident audit storage** (write-once) and regular reconciliation of `payments` against the bank.

**Token and loop limits:**

| Limit | Default | Where |
|---|---|---|
| Model requests per team run (shared by all delegated agents) | 40 (`AGENT_REQUEST_LIMIT`) | `UsageLimits` |
| Tool calls per team run | 60 (`AGENT_TOOL_CALLS_LIMIT`) | `UsageLimits` |
| Total tokens per team run | 150,000 (`AGENT_TOKEN_LIMIT`) | `UsageLimits` |
| Delegation depth | 3 hops; no self-calls or cycles | `ask_teammate` |
| Per-call timeout and retries | 90 s (`MODEL_TIMEOUT`), 2 retries | `config.get_model` |
| One team run at a time | `409` while busy | `/api/tickets/{id}/run` |
| Audit field size | 4,000 chars | `audit.clip` |

For scale, Problem 9 used 83k, 60k and 85k tokens per ticket, all within the 150k cap.

## 9. Results of the full run (Problem 9)

The working DB was reset first, with **starting checking at $3,400.00**. Tickets ran 101 → 102 → 103, and Desk manager approved on the desk.

| Ticket | First call | Agents (× = times called) | Hand-offs (plan → actual) | Human decisions | Cash change | Final |
|---|---|---|---|---|---|---|
| 101 tee | inventory | boss, inventory, accounting ×2, customer service | 3 → 4 | #1 pay invoice 501, **−$840**; #2 PO 1 tee ($8, no cash) | −$840.00 | resolved |
| 102 rent | facilities | boss, facilities, accounting ×2 | 2 → 3 | #3 pay rent, **−$2,400** | −$2,400.00 | resolved |
| 103 bulk | inventory | boss, inventory ×2, accounting ×2, customer service | 3 → 5 | none filed; marked resolved by Desk manager | $0.00 | resolved |

**Ending checking: $160.00.** That equals `cash_accounts.checking` in `campus_customs_new.db`, and $3,400 − (840 + 2,400) = $160. The itemized money map is on the **Cash** tab of `output/desk_tickets.html`. The per-ticket results are in `output/resolved_tickets.json`.

## 10. Lessons and known issues

- **Double-calling accounting.** On each ticket, the boss and a specialist both asked accounting. The tool's duplicate check stopped a second approval, but tokens were wasted. A fix would tell the boss not to delegate to a teammate a specialist will already call, or add a "pending delegation" check.
- **Ticket 103 was more cautious than planned.** The team filed no discount because the restock wasn't affordable. That's defensible, but the club got no price.
- **Portkey stall:** with `gpt-6-luna` through Portkey, `tool_choice="required"` after a long tool reply stalled every time. The fix was `NativeOutput` (JSON-schema output).
- **Auto-resolve override (fixed):** the backend once resolved 103 although the boss said `waiting_on_human`. The boss's status is now respected, and **Mark resolved** closes such tickets.
- **Timestamps:** the audit trail's `at` values show a UTC offset change partway through the session (−06:00, then −05:00), which comes from the host clock's settings. Business dates always come from `desk.date_today`.

## 11. File map

| Path | What |
|---|---|
| `requirements.txt` | One Python environment for the MCP server, agents and backend |
| `mcp_server/server.py`, `db_tools.py`, `smoke_test.py`, `README.md` | The MCP server, its tools, and the tool smoke test |
| `.mcp.json` | MCP registration for the vibe coder |
| `backend/config.py`, `models.py`, `agents/*.py`, `prompts/*.md` | Model and limits, data types, the five agents, their prompts |
| `backend/team.py`, `chat.py`, `audit.py`, `shop_client.py`, `main.py`, `README.md` | Agent loop, CLI, audit writer, human MCP client, FastAPI |
| `frontend/src/*` | React desk |
| `output/harness.md` | This file |
| `output/design.md` | Dashboard design rationale |
| `output/desk_tickets.html` | Expected vs actual per ticket, plus the Cash tab |
| `output/resolved_tickets.json` | Per-ticket results |
| `output/resolved_board.html` | Board screenshots for 101, 102 and 103 |
| `output/mcp_smoke.json` | MCP tool evidence |
| `output/audit_trail.json` | Append-only agent audit trail |
| `AI_prompts.md` | The prompt log |

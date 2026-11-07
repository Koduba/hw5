"""Database logic behind the Campus Customs MCP tools.

Every function reads only what is stored in the working copy of the shop
database. Nothing is invented: unknown SKUs, vendors, etc. come back as an
explicit error instead of a guess.

Shop rules enforced here (not just in prompts):
- "Today" is desk.date_today, never the system clock.
- A vendor with an open invoice will not ship.
- Money only leaves through an approval a HUMAN decided; agents can request
  but never approve. The pay tool refuses if cash would go negative.
- Customer/vendor/landlord messages are drafts on the board, never sent.

The original schema has no place for approvals or board drafts, so two
operating tables (`approvals`, `board`) are created in the working copy on
first write. Resetting copies the original back, which clears them too.
"""

import json
import os
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

HW5_DIR = Path(__file__).resolve().parent.parent
ORIGINAL_DB = HW5_DIR / "data" / "campus_customs.db"
WORKING_DB = HW5_DIR / "data" / "campus_customs_new.db"

TICKET_STATUSES = ("open", "in_progress", "waiting_on_human", "resolved")
DRAFT_AUDIENCES = ("customer", "vendor", "landlord", "internal")

OPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- payment | purchase_order | discount
    ticket_id INTEGER,
    summary TEXT NOT NULL,
    amount REAL NOT NULL,
    details TEXT NOT NULL,           -- JSON with the exact rows/values used
    requested_by TEXT NOT NULL,      -- agent name
    status TEXT NOT NULL,            -- pending | approved | rejected | executed
    decided_by TEXT,                 -- human name, set only by decide_approval
    decision_note TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    executed_at TEXT
);
CREATE TABLE IF NOT EXISTS board (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    author TEXT NOT NULL,
    kind TEXT NOT NULL,              -- draft | note
    audience TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------- plumbing

def db_path() -> Path:
    """Working-copy path; override with CAMPUS_DB_PATH. Never the original."""
    path = Path(os.getenv("CAMPUS_DB_PATH", WORKING_DB)).resolve()
    if path == ORIGINAL_DB.resolve():
        raise RuntimeError("Refusing to use the original campus_customs.db; point at the working copy.")
    if not path.exists():
        raise FileNotFoundError(f"Working database not found: {path}")
    return path


def connect(read_only: bool = True) -> sqlite3.Connection:
    mode = "ro" if read_only else "rw"
    conn = sqlite3.connect(f"file:{db_path()}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    if not read_only:
        conn.executescript(OPS_SCHEMA)
    return conn


def has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


def shop_today(conn: sqlite3.Connection) -> str:
    """The shop's 'today' comes from desk.date_today, not the system clock."""
    return conn.execute("SELECT date_today FROM desk").fetchone()["date_today"]


def days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def now_stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def add_month(iso_day: str) -> str:
    """Same day next month (clamped to month end), for advancing lease.next_due."""
    d = date.fromisoformat(iso_day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    raise ValueError(iso_day)


def reset_working_db() -> dict:
    """Copy the untouched original over the working copy. Human/admin only: no agent gets this tool."""
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    return {"reset": True, "working_db": str(WORKING_DB)}


def _approval_row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["details"] = json.loads(d["details"])
    return d


def _open_invoices(conn, vendor_id: int, today: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
        (vendor_id,),
    ).fetchall()
    return [{**dict(r), "days_overdue": max(days_between(r["due_date"], today), 0)} for r in rows]


def _active_request(conn, kind: str, key: str, value) -> dict | None:
    """An existing pending/approved request for the same thing (prevents duplicates)."""
    for r in conn.execute(
        "SELECT * FROM approvals WHERE kind = ? AND status IN ('pending', 'approved')", (kind,)
    ):
        if json.loads(r["details"]).get(key) == value:
            return _approval_row(r)
    return None


# ------------------------------------------------------------ read tools

def list_open_tickets() -> dict:
    """Return every ticket that is not resolved, oldest first, plus the shop date."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at"
        ).fetchall()
        return {"shop_date": shop_today(conn), "tickets": [dict(r) for r in rows]}


def get_ticket(ticket_id: int) -> dict:
    """Return one ticket with every row it links to: stock, pricing, invoice + vendor, lease,
    plus any approvals and board posts already filed for it."""
    with connect() as conn:
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if not t:
            return {"error": f"Ticket {ticket_id} does not exist."}
        today = shop_today(conn)
        out = {"shop_date": today, "ticket": dict(t)}
        if t["sku"]:
            out["stock"] = [dict(r) for r in conn.execute(
                "SELECT size, qty, location FROM inventory WHERE sku = ? ORDER BY size", (t["sku"],))]
            p = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (t["sku"],)).fetchone()
            out["pricing"] = dict(p) if p else None
        if t["invoice_id"]:
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (t["invoice_id"],)).fetchone()
            if inv:
                out["invoice"] = {**dict(inv), "days_overdue": max(days_between(inv["due_date"], today), 0)}
                out["invoice_vendor"] = dict(conn.execute(
                    "SELECT * FROM vendors WHERE id = ?", (inv["vendor_id"],)).fetchone())
        if t["lease_id"]:
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (t["lease_id"],)).fetchone()
            if lease:
                out["lease"] = {**dict(lease), "days_until_due": days_between(today, lease["next_due"])}
        if has_table(conn, "approvals"):
            out["approvals"] = [_approval_row(r) for r in conn.execute(
                "SELECT * FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
            out["board"] = [dict(r) for r in conn.execute(
                "SELECT * FROM board WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
        return out


def list_tickets(status: str | None = None) -> dict:
    """Return all tickets (any status), or only those with the given status, oldest first."""
    if status is not None and status not in TICKET_STATUSES:
        return {"error": f"status must be one of {TICKET_STATUSES}."}
    with connect() as conn:
        q, params = "SELECT * FROM tickets", []
        if status:
            q += " WHERE status = ?"
            params.append(status)
        rows = conn.execute(q + " ORDER BY created_at", params).fetchall()
        return {"shop_date": shop_today(conn), "tickets": [dict(r) for r in rows]}


def list_inventory() -> dict:
    """Return every SKU/size on hand with location, unit cost and list price."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT i.sku, i.name, i.size, i.qty, i.location, p.unit_cost, p.list_price "
            "FROM inventory i LEFT JOIN pricing p ON p.sku = i.sku ORDER BY i.sku, i.size"
        ).fetchall()
        return {"shop_date": shop_today(conn), "inventory": [dict(r) for r in rows]}


def check_stock(sku: str, size: str | None = None) -> dict:
    """Return on-hand quantity by size for a SKU, plus its unit cost and list price."""
    with connect() as conn:
        query, params = "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ?", [sku]
        if size:
            query += " AND size = ?"
            params.append(size)
        rows = conn.execute(query, params).fetchall()
        if not rows:
            what = f"SKU {sku} size {size}" if size else f"SKU {sku}"
            return {"error": f"{what} is not in inventory."}
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        return {
            "sku": sku,
            "stock": [dict(r) for r in rows],
            "pricing": dict(price) if price else None,
        }


def list_out_of_stock() -> dict:
    """Return every SKU/size with zero units on hand (shelf gaps to restock)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE qty <= 0 ORDER BY sku, size"
        ).fetchall()
        return {"shop_date": shop_today(conn), "out_of_stock": [dict(r) for r in rows]}


def get_vendor_status(vendor_id: int) -> dict:
    """Return a vendor's details and open invoices, and whether it will ship.

    Shop rule: a vendor will not ship while it has any open (unpaid) invoice.
    Days overdue are measured from desk.date_today.
    """
    with connect() as conn:
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            return {"error": f"Vendor {vendor_id} does not exist."}
        today = shop_today(conn)
        invoices = _open_invoices(conn, vendor_id, today)
        return {
            "shop_date": today,
            "vendor": dict(vendor),
            "open_invoices": invoices,
            "will_ship": not invoices,
        }


def list_vendors() -> dict:
    """Return every vendor with specialty, lead time, open-invoice total and whether it will ship."""
    with connect() as conn:
        today = shop_today(conn)
        vendors = []
        for v in conn.execute("SELECT * FROM vendors ORDER BY id"):
            invoices = _open_invoices(conn, v["id"], today)
            vendors.append({
                **dict(v),
                "open_invoice_ids": [i["id"] for i in invoices],
                "open_invoice_total": sum(i["amount"] for i in invoices),
                "will_ship": not invoices,
            })
        return {"shop_date": today, "vendors": vendors}


def list_open_invoices() -> dict:
    """Return all open invoices with vendor name, due date and days overdue (from desk.date_today)."""
    with connect() as conn:
        today = shop_today(conn)
        rows = conn.execute(
            "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
            "WHERE i.status = 'open' ORDER BY i.due_date"
        ).fetchall()
        invoices = [{**dict(r), "days_overdue": max(days_between(r["due_date"], today), 0),
                     "overdue": r["due_date"] < today} for r in rows]
        return {"shop_date": today, "open_invoices": invoices,
                "total_open": sum(i["amount"] for i in invoices)}


def get_lease(lease_id: int) -> dict:
    """Return a lease with monthly rent, next due date and days until due (from desk.date_today)."""
    with connect() as conn:
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if not lease:
            return {"error": f"Lease {lease_id} does not exist."}
        today = shop_today(conn)
        days = days_between(today, lease["next_due"])
        return {"shop_date": today, "lease": dict(lease), "days_until_due": days, "overdue": days < 0}


def get_cash_position() -> dict:
    """Return cash balances and what is already owed or awaiting approval.

    cash_after_commitments = balance - open invoices - rent due in the next 30 days
    - pending/approved payment requests not yet in those totals. Cash only goes out.
    """
    with connect() as conn:
        today = shop_today(conn)
        accounts = [dict(r) for r in conn.execute("SELECT * FROM cash_accounts")]
        balance = sum(a["balance"] for a in accounts)
        open_inv = sum(r["amount"] for r in conn.execute("SELECT amount FROM invoices WHERE status = 'open'"))
        rent_soon = [
            {**dict(r), "days_until_due": days_between(today, r["next_due"])}
            for r in conn.execute("SELECT id, space_name, monthly_rent, next_due FROM leases")
            if days_between(today, r["next_due"]) <= 30
        ]
        pending = []
        if has_table(conn, "approvals"):
            pending = [_approval_row(r) for r in conn.execute(
                "SELECT * FROM approvals WHERE status IN ('pending', 'approved') ORDER BY id")]
        rent_total = sum(r["monthly_rent"] for r in rent_soon)
        return {
            "shop_date": today,
            "accounts": accounts,
            "total_balance": balance,
            "open_invoices_total": open_inv,
            "rent_due_next_30_days": rent_soon,
            "rent_due_total": rent_total,
            "cash_after_commitments": round(balance - open_inv - rent_total, 2),
            "requests_awaiting_human_or_execution": pending,
        }


def check_margin(sku: str, qty: int, unit_price: float) -> dict:
    """Return revenue, cost and margin for selling qty units of a SKU at unit_price,
    compared with list price. Uses pricing.unit_cost; nothing is assumed."""
    if qty <= 0 or unit_price <= 0:
        return {"error": "qty and unit_price must be positive."}
    with connect() as conn:
        p = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if not p:
            return {"error": f"No pricing for SKU {sku}."}
        revenue, cost = unit_price * qty, p["unit_cost"] * qty
        return {
            "sku": sku, "qty": qty, "unit_price": unit_price,
            "unit_cost": p["unit_cost"], "list_price": p["list_price"],
            "discount_pct_vs_list": round(100 * (1 - unit_price / p["list_price"]), 2),
            "revenue": round(revenue, 2), "cost": round(cost, 2),
            "margin": round(revenue - cost, 2),
            "margin_pct": round(100 * (revenue - cost) / revenue, 2),
            "below_cost": unit_price < p["unit_cost"],
        }


def list_payments() -> dict:
    """Return every payment made (amount, account, what it paid, the human who approved it)."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM payments ORDER BY id").fetchall()
        return {"payments": [dict(r) for r in rows], "total_paid": sum(r["amount"] for r in rows)}


def list_approvals(status: str | None = None) -> dict:
    """Return approval requests, optionally filtered by status (pending/approved/rejected/executed)."""
    with connect() as conn:
        if not has_table(conn, "approvals"):
            return {"approvals": []}
        q, params = "SELECT * FROM approvals", []
        if status:
            q += " WHERE status = ?"
            params.append(status)
        return {"approvals": [_approval_row(r) for r in conn.execute(q + " ORDER BY id", params)]}


def list_board(ticket_id: int | None = None) -> dict:
    """Return drafts and notes on the board, optionally for one ticket."""
    with connect() as conn:
        if not has_table(conn, "board"):
            return {"board": []}
        q, params = "SELECT * FROM board", []
        if ticket_id is not None:
            q += " WHERE ticket_id = ?"
            params.append(ticket_id)
        return {"board": [dict(r) for r in conn.execute(q + " ORDER BY id", params)]}


# ----------------------------------------------- requests (need a human)

def request_payment(kind: str, ref_id: int, reason: str, requested_by: str,
                    ticket_id: int | None = None, account: str = "checking") -> dict:
    """File a payment request for a human to approve. kind is 'invoice' or 'lease'.

    The amount is read from the database (invoice amount or lease monthly_rent);
    agents cannot choose it. Nothing is paid here.
    """
    if kind not in ("invoice", "lease"):
        return {"error": "kind must be 'invoice' or 'lease'."}
    with connect(read_only=False) as conn:
        today = shop_today(conn)
        acct = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if not acct:
            return {"error": f"Cash account '{account}' does not exist."}
        if kind == "invoice":
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if not row:
                return {"error": f"Invoice {ref_id} does not exist."}
            if row["status"] != "open":
                return {"error": f"Invoice {ref_id} is '{row['status']}', not open; nothing to pay."}
            vendor = conn.execute("SELECT name FROM vendors WHERE id = ?", (row["vendor_id"],)).fetchone()
            amount = row["amount"]
            summary = f"Pay invoice {ref_id} to {vendor['name']}: ${amount:,.2f} ({row['description']}, due {row['due_date']})"
            details = {"kind": kind, "ref_id": ref_id, "invoice": dict(row), "vendor": vendor["name"]}
        else:
            row = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if not row:
                return {"error": f"Lease {ref_id} does not exist."}
            amount = row["monthly_rent"]
            summary = f"Pay rent for {row['space_name']} to {row['landlord']}: ${amount:,.2f} (due {row['next_due']})"
            details = {"kind": kind, "ref_id": ref_id, "lease": dict(row), "rent_period_due": row["next_due"]}
        dup = _active_request(conn, "payment", "ref_key", f"{kind}:{ref_id}:{details.get('rent_period_due', '')}")
        if dup:
            return {"error": "A request for this payment already exists.", "existing": dup}
        if amount > acct["balance"]:
            return {"error": f"Refused: ${amount:,.2f} exceeds {account} balance ${acct['balance']:,.2f}. "
                             "No negative balances."}
        details.update({"ref_key": f"{kind}:{ref_id}:{details.get('rent_period_due', '')}",
                        "account": account, "balance_at_request": acct["balance"],
                        "balance_after_if_paid": round(acct["balance"] - amount, 2),
                        "reason": reason, "shop_date": today})
        cur = conn.execute(
            "INSERT INTO approvals (kind, ticket_id, summary, amount, details, requested_by, status, created_at) "
            "VALUES ('payment', ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, summary, amount, json.dumps(details), requested_by, now_stamp()))
        return {"approval_id": cur.lastrowid, "status": "pending", "summary": summary,
                "note": "Waiting for a human to approve on the dashboard. Nothing has been paid."}


def request_purchase_order(vendor_id: int, sku: str, size: str, qty: int, reason: str,
                           requested_by: str, ticket_id: int | None = None) -> dict:
    """File a restock purchase order for a human to approve.

    Cost estimate = qty x pricing.unit_cost. ETA = desk.date_today + vendor lead_days.
    If the vendor has an open invoice it will not ship; the request is still filed
    but marked blocked, and it cannot be placed until that invoice is paid.
    """
    if qty <= 0:
        return {"error": "qty must be positive."}
    with connect(read_only=False) as conn:
        today = shop_today(conn)
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            return {"error": f"Vendor {vendor_id} does not exist."}
        item = conn.execute("SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        if not item:
            return {"error": f"SKU {sku} size {size} is not in inventory."}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if not price:
            return {"error": f"No pricing for SKU {sku}; cannot estimate cost."}
        blocking = _open_invoices(conn, vendor_id, today)
        amount = round(qty * price["unit_cost"], 2)
        eta = date.fromordinal(date.fromisoformat(today).toordinal() + vendor["lead_days"]).isoformat()
        summary = (f"Restock {qty} x {item['name']} ({sku} {size}) from {vendor['name']}: "
                   f"est. ${amount:,.2f}, ETA {eta} after placement")
        details = {"vendor": dict(vendor), "sku": sku, "size": size, "qty": qty,
                   "unit_cost": price["unit_cost"], "on_hand": item["qty"],
                   "eta_if_placed_today": eta, "blocked_by_open_invoices": [i["id"] for i in blocking],
                   "will_ship": not blocking, "reason": reason, "shop_date": today}
        cur = conn.execute(
            "INSERT INTO approvals (kind, ticket_id, summary, amount, details, requested_by, status, created_at) "
            "VALUES ('purchase_order', ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, summary, amount, json.dumps(details), requested_by, now_stamp()))
        out = {"approval_id": cur.lastrowid, "status": "pending", "summary": summary}
        if blocking:
            out["warning"] = (f"{vendor['name']} will not ship until invoice(s) "
                              f"{[i['id'] for i in blocking]} are paid.")
        return out


def request_discount(ticket_id: int, unit_price: float, reason: str, requested_by: str) -> dict:
    """File a discounted price for a ticket's SKU and qty for a human to approve.
    Margin is computed from pricing; the amount recorded is the discount given up vs list."""
    with connect(read_only=False) as conn:
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if not t:
            return {"error": f"Ticket {ticket_id} does not exist."}
        if not (t["sku"] and t["qty"]):
            return {"error": f"Ticket {ticket_id} has no SKU/qty to price."}
    margin = check_margin(t["sku"], t["qty"], unit_price)
    if "error" in margin:
        return margin
    with connect(read_only=False) as conn:
        give_up = round((margin["list_price"] - unit_price) * t["qty"], 2)
        summary = (f"Discount for ticket {ticket_id} ({t['requester']}): {t['qty']} x {t['sku']} {t['size'] or ''} "
                   f"at ${unit_price:,.2f} ({margin['discount_pct_vs_list']}% off list), "
                   f"margin ${margin['margin']:,.2f} ({margin['margin_pct']}%)")
        details = {"ticket_key": ticket_id, "margin": margin, "reason": reason,
                   "shop_date": shop_today(conn)}
        dup = _active_request(conn, "discount", "ticket_key", ticket_id)
        if dup:
            return {"error": "A discount request for this ticket already exists.", "existing": dup}
        cur = conn.execute(
            "INSERT INTO approvals (kind, ticket_id, summary, amount, details, requested_by, status, created_at) "
            "VALUES ('discount', ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, summary, give_up, json.dumps(details), requested_by, now_stamp()))
        out = {"approval_id": cur.lastrowid, "status": "pending", "summary": summary}
        if margin["below_cost"]:
            out["warning"] = "This price is below unit cost: the shop would lose money on every unit."
        return out


# ------------------------------- human decision (MCP tool, but given to NO agent)

def decide_approval(approval_id: int, decision: str, approver: str, note: str = "") -> dict:
    """Record a human's approve/reject. Only the dashboard/CLI calls this; no agent has this tool."""
    if decision not in ("approved", "rejected"):
        return {"error": "decision must be 'approved' or 'rejected'."}
    if not approver.strip():
        return {"error": "A human approver name is required."}
    with connect(read_only=False) as conn:
        r = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if not r:
            return {"error": f"Approval {approval_id} does not exist."}
        if r["status"] != "pending":
            return {"error": f"Approval {approval_id} is already '{r['status']}'."}
        conn.execute(
            "UPDATE approvals SET status = ?, decided_by = ?, decision_note = ?, decided_at = ? WHERE id = ?",
            (decision, approver.strip(), note, now_stamp(), approval_id))
        return {"approval_id": approval_id, "status": decision, "decided_by": approver.strip()}


# ------------------------------------------ execution (gated by approval)

def pay_approved_request(approval_id: int) -> dict:
    """Pay a payment request ONLY if a human approved it and cash covers it.

    In one transaction: deduct the cash account, insert a payments row with the
    human's name in approved_by, mark the invoice paid or move the lease's
    next_due forward one month, and mark the approval executed.
    """
    with connect(read_only=False) as conn:
        r = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if not r:
            return {"error": f"Approval {approval_id} does not exist."}
        if r["kind"] != "payment":
            return {"error": f"Approval {approval_id} is a {r['kind']}, not a payment."}
        if r["status"] == "executed":
            return {"error": f"Refused: approval {approval_id} was already executed."}
        if r["status"] != "approved" or not r["decided_by"]:
            return {"error": f"Refused: approval {approval_id} is '{r['status']}'. A human must approve it first."}
        d = json.loads(r["details"])
        today = shop_today(conn)
        acct = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (d["account"],)).fetchone()
        if r["amount"] > acct["balance"]:
            return {"error": f"Refused: ${r['amount']:,.2f} exceeds {d['account']} balance "
                             f"${acct['balance']:,.2f}. No negative balances."}
        if d["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (d["ref_id"],)).fetchone()
            if inv["status"] != "open":
                return {"error": f"Refused: invoice {d['ref_id']} is already '{inv['status']}'."}
        new_balance = round(acct["balance"] - r["amount"], 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                     (new_balance, today, d["account"]))
        pay = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (d["kind"], d["ref_id"], r["amount"], d["account"], today, r["decided_by"]))
        if d["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (d["ref_id"],))
            updated = f"invoice {d['ref_id']} marked paid"
        else:
            nxt = add_month(d["rent_period_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (nxt, d["ref_id"]))
            updated = f"lease {d['ref_id']} next_due moved to {nxt}"
        conn.execute("UPDATE approvals SET status = 'executed', executed_at = ? WHERE id = ?",
                     (now_stamp(), approval_id))
        return {"paid": True, "payment_id": pay.lastrowid, "amount": r["amount"],
                "approved_by": r["decided_by"], "account": d["account"],
                "balance_after": new_balance, "updated": updated}


def place_approved_purchase_order(approval_id: int) -> dict:
    """Place a human-approved restock order: re-check the vendor will ship, then post the
    PO to the board as a vendor draft (vendors are never contacted). Moves no cash."""
    with connect(read_only=False) as conn:
        r = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if not r or r["kind"] != "purchase_order":
            return {"error": f"Approval {approval_id} is not a purchase order."}
        if r["status"] == "executed":
            return {"error": f"Refused: approval {approval_id} was already executed."}
        if r["status"] != "approved" or not r["decided_by"]:
            return {"error": f"Refused: approval {approval_id} is '{r['status']}'. A human must approve it first."}
        d = json.loads(r["details"])
        today = shop_today(conn)
        blocking = _open_invoices(conn, d["vendor"]["id"], today)
        if blocking:
            return {"error": f"Refused: {d['vendor']['name']} will not ship while invoice(s) "
                             f"{[i['id'] for i in blocking]} are open. Pay them first."}
        eta = date.fromordinal(date.fromisoformat(today).toordinal() + d["vendor"]["lead_days"]).isoformat()
        body = (f"Purchase order (approved by {r['decided_by']}): {d['qty']} x {d['sku']} size {d['size']} "
                f"at ${d['unit_cost']:,.2f} = ${r['amount']:,.2f}. Expected by {eta} "
                f"({d['vendor']['lead_days']}-day lead time).")
        conn.execute(
            "INSERT INTO board (ticket_id, author, kind, audience, subject, body, created_at) "
            "VALUES (?, 'system', 'draft', 'vendor', ?, ?, ?)",
            (r["ticket_id"], f"PO to {d['vendor']['name']}", body, now_stamp()))
        conn.execute("UPDATE approvals SET status = 'executed', executed_at = ? WHERE id = ?",
                     (now_stamp(), approval_id))
        return {"placed": True, "vendor": d["vendor"]["name"], "eta": eta, "draft_on_board": body}


# ------------------------------------------------- board + ticket updates

def post_draft(ticket_id: int, author: str, audience: str, subject: str, body: str) -> dict:
    """Post a DRAFT message (customer, vendor, landlord or internal) to the board.
    Drafts are never sent; a human reads them on the dashboard."""
    if audience not in DRAFT_AUDIENCES:
        return {"error": f"audience must be one of {DRAFT_AUDIENCES}."}
    with connect(read_only=False) as conn:
        if not conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone():
            return {"error": f"Ticket {ticket_id} does not exist."}
        cur = conn.execute(
            "INSERT INTO board (ticket_id, author, kind, audience, subject, body, created_at) "
            "VALUES (?, ?, 'draft', ?, ?, ?, ?)",
            (ticket_id, author, audience, subject, body, now_stamp()))
        return {"board_id": cur.lastrowid, "posted": "draft", "sent": False}


def update_ticket(ticket_id: int, status: str, note: str, author: str) -> dict:
    """Set a ticket's status (open, in_progress, waiting_on_human, resolved) and log a note on the board.
    A ticket cannot be resolved while it still has a pending approval."""
    if status not in TICKET_STATUSES:
        return {"error": f"status must be one of {TICKET_STATUSES}."}
    with connect(read_only=False) as conn:
        t = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if not t:
            return {"error": f"Ticket {ticket_id} does not exist."}
        if status == "resolved":
            pending = [r["id"] for r in conn.execute(
                "SELECT id FROM approvals WHERE ticket_id = ? AND status = 'pending'", (ticket_id,))]
            if pending:
                return {"error": f"Cannot resolve ticket {ticket_id}: approvals {pending} still need a human."}
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.execute(
            "INSERT INTO board (ticket_id, author, kind, audience, subject, body, created_at) "
            "VALUES (?, ?, 'note', 'internal', ?, ?, ?)",
            (ticket_id, author, f"Status {t['status']} -> {status}", note, now_stamp()))
        return {"ticket_id": ticket_id, "old_status": t["status"], "status": status}

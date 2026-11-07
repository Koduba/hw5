"""Smoke test: call each MCP tool through .mcp.json and check its output against the DB.

Run from hw5/:  .venv/bin/python mcp_server/smoke_test.py
Writes output/mcp_smoke.json. Expected values come from SQL run directly
against data/campus_customs_new.db, not from the server's own code.
"""

import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from fastmcp import Client

HW5 = Path(__file__).resolve().parent.parent
DB = HW5 / "data" / "campus_customs_new.db"
OUT = HW5 / "output" / "mcp_smoke.json"

REQUEST = (
    "lets test each of your three MCP tools. Save the evidence in output/mcp_smoke.json. "
    "For every tool, include the prompt I asked, the tool name, the tool output must match "
    "values in data/campus_customs_new.db."
)


def sql(query, params=()):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(query, params)]
    conn.close()
    return rows


def expect_open_tickets(_out):
    return {
        "shop_date": sql("SELECT date_today FROM desk")[0]["date_today"],
        "tickets": sql("SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at"),
    }, ["SELECT date_today FROM desk",
        "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at"]


def expect_stock(sku, size):
    def check(_out):
        stock = sql("SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?", (sku, size))
        price = sql("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
        return {"sku": sku, "stock": stock, "pricing": price[0] if price else None}, [
            f"SELECT sku, name, size, qty, location FROM inventory WHERE sku = '{sku}' AND size = '{size}'",
            f"SELECT unit_cost, list_price FROM pricing WHERE sku = '{sku}'",
        ]
    return check


def expect_vendor(vendor_id):
    def check(_out):
        q = ("SELECT i.*, CAST(julianday(d.date_today) - julianday(i.due_date) AS INTEGER) AS days_overdue "
             "FROM invoices i, desk d WHERE i.vendor_id = ? AND i.status = 'open' ORDER BY i.due_date")
        invoices = sql(q, (vendor_id,))
        for inv in invoices:
            inv["days_overdue"] = max(inv["days_overdue"], 0)
        return {
            "shop_date": sql("SELECT date_today FROM desk")[0]["date_today"],
            "vendor": sql("SELECT * FROM vendors WHERE id = ?", (vendor_id,))[0],
            "open_invoices": invoices,
            "will_ship": len(invoices) == 0,
        }, [f"SELECT * FROM vendors WHERE id = {vendor_id}", q.replace("?", str(vendor_id))]
    return check


TESTS = [
    {"ticket": [101, 102, 103], "prompt": "Which tickets are open on the board right now, and what is the shop's date?",
     "tool": "list_open_tickets", "arguments": {}, "expect": expect_open_tickets},
    {"ticket": [101], "prompt": "Ticket 101: do we have a Classic Bulldog Tee (CC-TEE-WHITE) in size S on the shelf?",
     "tool": "check_stock", "arguments": {"sku": "CC-TEE-WHITE", "size": "S"}, "expect": expect_stock("CC-TEE-WHITE", "S")},
    {"ticket": [103], "prompt": "Ticket 103: how many navy hoodies (CC-HOOD-NAVY) in size M do we have for the Yale AI Club's 20, and what do they cost us?",
     "tool": "check_stock", "arguments": {"sku": "CC-HOOD-NAVY", "size": "M"}, "expect": expect_stock("CC-HOOD-NAVY", "M")},
    {"ticket": [101, 103], "prompt": "Can Bulldog Print Co (vendor 1) restock apparel right now, or do we owe them money?",
     "tool": "get_vendor_status", "arguments": {"vendor_id": 1}, "expect": expect_vendor(1)},
]


async def main():
    sys.path.insert(0, str(HW5))
    from backend.config import mcp_client_config  # resolves .mcp.json's relative paths
    config = mcp_client_config()
    results = []
    async with Client(config) as client:
        listed = sorted(t.name for t in await client.list_tools())
        for t in TESTS:
            res = await client.call_tool(t["tool"], t["arguments"])
            output = res.structured_content
            expected, queries = t["expect"](output)
            results.append({
                "tickets": t["ticket"],
                "prompt": t["prompt"],
                "tool": t["tool"],
                "arguments": t["arguments"],
                "tool_output": output,
                "db_check": {"queries": queries, "expected_from_db": expected, "match": output == expected},
            })
    report = {
        "requested_by_prompt": REQUEST,
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "transport": "stdio via .mcp.json (server: campus-customs)",
        "database": "data/campus_customs_new.db",
        "tools_listed_by_server": listed,
        "all_match": all(r["db_check"]["match"] for r in results),
        "tests": results,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    for r in results:
        print(f"{'PASS' if r['db_check']['match'] else 'FAIL'}  {r['tool']}({r['arguments']})")
    print("all_match:", report["all_match"])


if __name__ == "__main__":
    asyncio.run(main())

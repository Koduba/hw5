"""Talk to any agent in your own words, run a ticket, or act as the human approver.

From hw5/:
    .venv/bin/python -m backend.chat inventory "Do we have the white tee in small?"
    .venv/bin/python -m backend.chat --ticket 101
    .venv/bin/python -m backend.chat --approvals                    # what is waiting on a human
    .venv/bin/python -m backend.chat --approve 2 --by "Your Name"   # approve (and execute) via MCP
    .venv/bin/python -m backend.chat --reject 3 --by "Your Name"
    .venv/bin/python -m backend.chat --reset                        # working DB <- original
"""

import argparse
import asyncio
import json

from .models import AGENT_NAMES


def main() -> None:
    p = argparse.ArgumentParser(description="Campus Customs agent team")
    p.add_argument("agent", nargs="?", choices=AGENT_NAMES)
    p.add_argument("message", nargs="?", help="What you want to ask, in your own words")
    p.add_argument("--ticket", type=int, help="Run this ticket through the boss")
    p.add_argument("--approvals", action="store_true", help="List approval requests")
    p.add_argument("--approve", type=int, metavar="ID", help="Approve a request (human only)")
    p.add_argument("--reject", type=int, metavar="ID", help="Reject a request (human only)")
    p.add_argument("--by", help="Your name, recorded as the approver")
    p.add_argument("--reset", action="store_true", help="Copy campus_customs.db over the working copy")
    p.add_argument("--trace", action="store_true", help="Print every step of the run")
    a = p.parse_args()

    from . import shop_client  # human/admin actions go through the same MCP server

    if a.reset:
        print(asyncio.run(shop_client.call_tool("reset_working_db")))
        return
    if a.approvals:
        print(json.dumps(asyncio.run(shop_client.call_tool("list_approvals")), indent=2))
        return
    if a.approve or a.reject:
        if not a.by:
            p.error("--by is required: a human name is recorded on every decision")
        decision, aid = ("approved", a.approve) if a.approve else ("rejected", a.reject)
        print(json.dumps(asyncio.run(shop_client.decide(aid, decision, a.by)), indent=2))
        return

    from .team import ask, run_ticket  # imported late so the human commands don't load the model

    if a.ticket is not None:
        result = asyncio.run(run_ticket(a.ticket))
    elif a.agent and a.message:
        result = asyncio.run(ask(a.agent, a.message))
    else:
        p.error("give an agent and a message, or --ticket N, --approvals, --approve/--reject, --reset")

    if a.trace:
        for e in result.trace:
            print(f"{e.step:>3} {'  ' * e.depth}[{e.agent}] {e.kind}: {json.dumps(e.data, default=str)[:240]}")
        print()
    print(result.output.model_dump_json(indent=2))
    print(f"\n(run {result.run_id}: {result.requests} model requests, {result.total_tokens} tokens; "
          f"{len(result.trace)} steps appended to output/audit_trail.json)")


if __name__ == "__main__":
    main()

# Campus Customs Ops Desk: design notes

The dashboard (`frontend/`, React + Vite + TypeScript) is where a person sits to watch five AI agents run a small shop, and to be the one human who says yes or no when money is involved. Every design choice below serves one idea:

> **It should feel like a calm, well-lit desk at night: the agents do the legwork in front of you, and the only thing that ever asks for your attention is a decision that's actually yours.**

## How it connects

- **Address:** the page runs at `http://localhost:5173` and calls the FastAPI backend directly at **`http://localhost:8000`**. The address is set in `src/api.ts` and can be changed with `VITE_API_URL`; see `frontend/.env.example`.
- **CORS:** the backend allows only the desk's origin (`http://localhost:5173` and `127.0.0.1:5173`, configurable with `DASHBOARD_ORIGINS`), and only `GET` and `POST`. A preflight from any other origin is refused with `400`.
- **Starting it:** `npm run dev` in `frontend/` starts Vite and opens the desk in your browser. Start the backend first: `uvicorn main:app --reload --port 8000` from `backend/`.
- **Refresh rates:** the desk refreshes shop state every 3 s. While a run is going, it streams agent steps every 1.2 s using the `since` cursor from `/api/events`, so it only fetches what's new.

## The look

| Choice | Why |
|---|---|
| **Near-black background** (`#08080c`) with a faint 32px grid that fades out toward the edges | It feels like a desk surface or a control room rather than a web page. Dark is easier on the eyes for a screen left open all day, and it makes the colored "lights" of the agents read clearly. |
| **Hot pink (`#ff3ea5`) as the one action color** | Pink only means "this is live" or "this is yours to act on": the Run button, the selected ticket, pending approvals, the live dot. Because it's used sparingly, your eye goes straight to what matters. It's also our house style: a polished black-and-pink look. |
| **Two soft radial glows** (pink top-right, violet bottom-left) under frosted, slightly translucent panels | They add depth without clutter, so the panels feel like they sit *on* the desk rather than being boxes on a page. |
| **Big, tight headings; small uppercase section labels** (QUEUE, AGENT FLOOR, CHECKING) | They give a clear order of importance: the ticket title and the cash balance are the two biggest things on screen, because they're what you came to see. |
| **Monospace only for data** (SKUs, tool names, run IDs) | Anything that comes from the machine (`check_stock`, `CC-TEE-WHITE · S · ×1`) looks different from human words, so you can always tell a fact from a sentence. |
| **Tabular numbers everywhere money appears** | Digits stay aligned as values change, so a dollar amount never jitters while it animates. |

## The layout: three columns, read left to right

```
┌──────────────┬───────────────────────────────────┬───────────────────┐
│ QUEUE        │ TICKET FOCUS   [▶ Run the team]   │ CHECKING  $3,400  │
│  #101 tee    │ "Needs a tee in size S."          │ ▓▓▓▓▓▓▓▓▓▓▓▓░     │
│  #102 rent   ├───────────────────────────────────┤ NEEDS YOUR OK (1) │
│  #103 bulk   │ AGENT FLOOR                       │  💸 $840 [Approve]│
│              │          [ Boss ]                 │ DRAFTS            │
│              │ [Inv] [Acct] [Facil] [Cust Svc]   │  ✉ to Tauhid  DRAFT│
│              ├───────────────────────────────────┤                   │
│              │ Live feed | What each agent did   │                   │
└──────────────┴───────────────────────────────────┴───────────────────┘
```

It follows the way the work flows. **What's waiting** is on the left (the queue), **what's happening** is in the middle (the agents), and **what it costs and what you must decide** is on the right (cash, approvals, drafts). The side columns stay fixed while the center scrolls, so cash and your approval inbox never leave view during a long run. On narrower screens the right column moves under the center, and on phones everything stacks into one column.

## How the agents read differently

Each agent has a **color and a symbol**. The same pair shows up on its station, in the live feed, and in the report, so you learn them without trying:

| Agent | Color | Symbol | Why |
|---|---|---|---|
| Boss | pink `#ff3ea5` | ★ | The boss gets the house color, and a star for "makes the call" |
| Inventory | violet | ▦ | A grid of shelves |
| Accounting | green | $ | Money is green, and it matches the cash card |
| Facilities | amber | ⌂ | A building, in a warm "property" tone |
| Customer service | sky blue | ✉ | A letter: calm, friendly, outward-facing |

**The agent floor is shaped like the team.** The boss sits alone in a wide station on top, with a thin pink line down to the four specialists below. You can see the org chart without a diagram.

**Each station shows its state four ways at once:**
- **A state badge:** *Thinking* or *Using a tool* (filled in the agent's color), *Waiting on a teammate* (outlined), *Done* (green), or *Off this ticket* (dimmed).
- **A speech bubble** with what the agent is doing right now, in plain words: "Checking stock — CC-TEE-WHITE · S" or "→ Accounting: Ticket 101, requester Tauhid…". Raw tool names are translated into verbs, and JSON reports are reduced to their one-sentence summary.
- **Glow and motion:** the active agent lifts slightly, its border lights up in its color, and its avatar "breathes". A station waiting on a teammate gets a dashed border, like a line on hold.
- **Footer tags:** who asked it ("asked by Boss"), its current tool, and how many tool calls it has made.

**Agents that aren't needed stay visibly idle.** On a rent ticket, Inventory and Customer Service sit dimmed with "Not needed on this ticket." That makes the boss's routing choices visible at a glance, which helps when comparing against the plan in `desk_tickets.html`.

**The header line spells out the hand-offs** ("Boss → Facilities · Facilities → Accounting"). In the live feed, delegated work is **indented by depth**, so a specialist asking another specialist looks like a nested conversation.

## How a ticket gets resolved

The rule says **every payment needs a person**, so "the run finished" and "the ticket is resolved" are not always the same moment. The desk is honest about the difference:

- **Status pills** on each ticket card: `Open` → **`Agents working`** (with a pink line sweeping along the card's bottom edge) → **`Needs your OK`** (pink, with "1 approval waiting") → **`Resolved`** (green, and the title gets a soft green strike-through, like crossing an item off a to-do list).
- **When a run ends**, a banner under the ticket says one of two things:
  - ✓ **Resolved.** The run finished and nothing is waiting on a human. The backend marks the ticket resolved right away.
  - ⏳ **Run finished. Waiting on you.** It points you to the inbox on the right. The ticket resolves **by itself** the moment you decide the last approval.
- **A toast** at the bottom confirms each outcome ("Ticket #101 resolved." or "Paid $840.00 · checking $3,400.00 → $2,560.00").
- **The center switches to "What each agent did"** when a run ends. It shows the boss's decision, a **"What you need to do"** checklist, and one card per agent with a colored top edge, its summary, the tools it used, its hand-offs, the approvals and drafts it filed, and its token count. An agent called more than once gets an amber **"called ×2"** tag, because repeated work is worth noticing.

## How cash shows up

Cash is the one number that can't be wrong, so it gets the biggest type on the screen and its own card at the top right.

- **The balance is huge** (42px, heavy weight). It comes from `cash_accounts.checking` through `/api/cash`.
- **It animates when it moves.** After an approved payment the number counts down (with an ease-out curve) from $3,400.00 to $2,560.00, flashes red once, and shows a **"−$840.00" chip** for a few seconds. You see the money leave, which makes the approval feel as real as it is.
- **A three-part bar** shows **paid out** (grey), **still owed** (pink, invoices plus rent due) and **free after commitments** (green). At the start that's $0 / $3,240 / $160: one glance shows the shop is nearly fully committed.
- **A ledger** under the bar lists every payment with **the name of the person who approved it**, mirroring `payments.approved_by`.
- **Each payment card in the inbox shows "Checking after: $X"** before you click, and turns red if the payment would go negative (the pay tool would refuse it anyway).
- **A footnote** says it plainly: *"Cash only moves when a person approves a payment."*

## The approval inbox: designed for one careful click

- **The title is "Needs your OK"**, not "Approvals". It speaks to the person, and a pink count badge pops in when something arrives. The whole panel glows pink while anything is pending.
- **Each request is a card** with an icon and a colored left edge for its kind: 💸 payment (pink), 📦 purchase order (violet), 🏷️ discount (amber). It shows the amount in large type, the agent's summary, **who asked and why** (the agent's own reason, in quotes), and what happens next.
- **The buttons say what they do:** **Approve & pay**, **Approve & place PO**, **Approve price**. "Approve & pay" tells you this click moves money. **Reject** sits beside it as a quieter outlined button.
- **The buttons stay disabled until you type your name** in **On desk** in the top bar, because that name is recorded as `approved_by`. It's kept in the browser, so you only type it once. This is a small piece of friction on purpose: nobody approves money anonymously.
- **Warnings are written in plain words:** a purchase order whose vendor is still blocked by an unpaid invoice says so before you click.
- **Decided requests** collapse into a short history with green *executed*, green *approved* or red *rejected* pills, plus the decider's name.

## Drafts: real messages that are clearly not sent

Drafts appear as compact rows: an audience icon (🧑‍🎓 customer, 🏢 landlord, 🏭 vendor), the subject, and a slightly tilted pink **DRAFT** stamp, like a rubber stamp on paper. Click a row to read the body. Nothing on the desk can send a message, and the stamp keeps that visible.

## Small touches that make it pleasant to use

- **The team status pill in the top bar** pulses pink while agents are working ("Team working on **#101** · Bulldog tee") and goes quiet when they're idle. It says "Backend offline" in red if `:8000` isn't up, with the command to fix it.
- **The shop date sits next to your name** as a constant reminder that the shop's "today" is `desk.date_today`, not your calendar.
- **The live feed follows new steps inside its own scroll area** and never yanks the page. New lines slide up gently. Each line has a timestamp, the agent's colored symbol, a plain-language action, and the exact tool and arguments in small monospace for anyone who wants to check.
- **The Run button changes its words:** "Run the agent team", then "Team is on it…" with a spinner, then "Re-run the team". It's disabled while another ticket runs, with a note that the team works one ticket at a time, because they share one budget and one cash balance.
- **Reset shop** asks before wiping, and says the audit trail is kept.
- **Accessibility:**
  - visible pink focus rings and real buttons for every control;
  - `aria-live` on the feed, team status and cash;
  - plain-language state labels as well as colors, so color is never the only signal;
  - animations switched off for anyone who prefers reduced motion.

## Why this works for a real person

1. **Attention is precious, so it is rationed.** Pink and motion are reserved for "live" and "yours to decide". Everything else is calm.
2. **Seeing the work builds trust.** You watch Inventory check the shelf and Accounting check the cash before anything is asked of you, so the approval card arrives with its reasons already visible.
3. **Money feels like money.** It's big, it animates, it has a name attached, and the click that moves it says so.
4. **The agents feel like colleagues, not log lines.** Each has a color, a seat, a voice bubble and a status, which makes a five-agent system readable in seconds.
5. **Honest states.** "Run finished. Waiting on you" is different from "Resolved", and the desk never blurs the two.

import type { AgentEvent, AgentName } from "./types";

export const AGENT_META: Record<AgentName, { label: string; role: string; icon: string; color: string }> = {
  boss: { label: "Boss", role: "Routes tickets · makes the call", icon: "★", color: "#ff3ea5" },
  inventory: { label: "Inventory", role: "Stock by SKU & size · vendors", icon: "▦", color: "#a78bfa" },
  accounting: { label: "Accounting", role: "Cash · invoices · margins", icon: "$", color: "#4ade80" },
  facilities: { label: "Facilities", role: "Lease · rent · the shop", icon: "⌂", color: "#fbbf24" },
  customer_service: { label: "Customer Service", role: "Drafts customer replies", icon: "✉", color: "#38bdf8" },
};

const TOOL_VERBS: Record<string, string> = {
  list_open_tickets: "Scanning the open tickets",
  list_tickets: "Scanning all tickets",
  get_ticket: "Reading the ticket",
  check_stock: "Checking stock",
  list_inventory: "Scanning inventory",
  list_out_of_stock: "Looking for shelf gaps",
  get_vendor_status: "Checking the vendor",
  list_vendors: "Comparing vendors",
  list_open_invoices: "Reviewing open invoices",
  get_lease: "Reading the lease",
  get_cash_position: "Checking cash",
  check_margin: "Running margin math",
  list_payments: "Checking payments",
  list_approvals: "Checking approvals",
  list_board: "Checking the board",
  request_payment: "Filing a payment request",
  request_purchase_order: "Drafting a purchase order",
  request_discount: "Filing a discount request",
  pay_approved_request: "Paying an approved request",
  place_approved_purchase_order: "Placing an approved PO",
  post_draft: "Writing a draft",
  update_ticket: "Updating the ticket",
  ask_teammate: "Asking a teammate",
};

export function toolVerb(tool: string | null): string {
  return tool ? TOOL_VERBS[tool] ?? tool.replace(/_/g, " ") : "";
}

export function agentLabel(a: string): string {
  return AGENT_META[a as AgentName]?.label ?? a;
}

/** Short readable form of tool args, e.g. "CC-TEE-WHITE · S". */
export function argsBrief(args: AgentEvent["args"]): string {
  if (!args || typeof args === "string") return args ?? "";
  const skip = new Set(["requested_by", "author", "reason", "note", "body"]);
  return Object.entries(args)
    .filter(([k, v]) => !skip.has(k) && v !== null && v !== "")
    .map(([k, v]) => (typeof v === "string" && v.length > 40 ? `${k}: ${v.slice(0, 40)}…` : `${v}`))
    .join(" · ");
}

/** If `said` is a JSON report, pull out its human sentence. */
export function readable(said: string | null): string | null {
  if (!said) return null;
  const t = said.trim();
  const arrow = t.match(/^(←|→) ?([a-z_]+): ([\s\S]*)$/);
  const body = arrow ? arrow[3] : t;
  if (body.startsWith("{")) {
    try {
      const o = JSON.parse(body);
      const text = o.decision ?? o.summary;
      if (text) return arrow ? `${arrow[1]} ${agentLabel(arrow[2])}: ${text}` : text;
    } catch {
      const m = body.match(/"(?:summary|decision)"\s*:\s*"((?:[^"\\]|\\.)*)/);
      if (m) return arrow ? `${arrow[1]} ${agentLabel(arrow[2])}: ${m[1]}` : m[1];
      return null;
    }
  }
  return arrow ? `${arrow[1]} ${agentLabel(arrow[2])}: ${body}` : t;
}

export type AgentState = "idle" | "thinking" | "working" | "delegating" | "waiting" | "done" | "error";

export interface Station {
  state: AgentState;
  line: string | null;
  tool: string | null;
  askedBy: AgentName | null;
  tools: number;
}

/** Fold one run's events into what each agent is doing right now. */
export function stations(events: AgentEvent[]): Record<AgentName, Station> {
  const s = {} as Record<AgentName, Station>;
  for (const a of Object.keys(AGENT_META) as AgentName[]) {
    s[a] = { state: "idle", line: null, tool: null, askedBy: null, tools: 0 };
  }
  for (const e of events) {
    const st = s[e.agent];
    if (!st) continue;
    switch (e.kind) {
      case "start":
        st.state = "thinking";
        st.askedBy = e.chain && e.chain.length > 1 ? e.chain[e.chain.length - 2] : null;
        st.line = st.askedBy ? `Picked up a request from ${agentLabel(st.askedBy)}` : "Reading the ticket";
        break;
      case "model_response":
        if (st.state !== "delegating") st.state = "thinking";
        break;
      case "tool_call":
        st.state = "working";
        st.tool = e.tool;
        st.tools += 1;
        st.line = `${toolVerb(e.tool)}${argsBrief(e.args) ? ` — ${argsBrief(e.args)}` : ""}`;
        break;
      case "delegate":
        st.state = "delegating";
        st.tool = "ask_teammate";
        st.line = readable(e.said);
        break;
      case "delegate_reply":
        st.state = "thinking";
        st.line = readable(e.said);
        break;
      case "refused":
        st.line = `Blocked: ${e.said}`;
        break;
      case "finish":
        st.state = "done";
        st.tool = null;
        st.line = readable(e.said);
        break;
      case "error":
        st.state = "error";
        st.line = e.said;
        break;
    }
  }
  return s;
}

export function money(n: number | null | undefined): string {
  return (n ?? 0).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function timeOf(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

export const TICKET_ICON: Record<string, string> = {
  customer_order: "👕",
  rent_notice: "🏠",
  price_override: "🏷️",
};

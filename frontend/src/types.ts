// Shapes returned by the Problem 7 FastAPI routes (backend/main.py).

export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";
export const AGENTS: AgentName[] = ["boss", "inventory", "accounting", "facilities", "customer_service"];

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  status: "open" | "in_progress" | "waiting_on_human" | "resolved";
  state: "open" | "resolved";
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  notes: string | null;
  created_at: string;
}

export interface AgentEvent {
  index: number;
  at: string;
  run_id: string;
  step: number;
  agent: AgentName;
  depth: number;
  chain: AgentName[] | null;
  ticket_id: number | null;
  kind: "start" | "model_request" | "model_response" | "tool_call" | "tool_result" | "delegate"
    | "delegate_reply" | "refused" | "finish" | "error";
  said: string | null;
  tool: string | null;
  args: Record<string, unknown> | string | null;
}

export interface EventsPage {
  total: number;
  next: number;
  events: AgentEvent[];
}

export interface BossDecision {
  ticket_id: number | null;
  assigned_to: AgentName[];
  decision: string;
  reasons: string[];
  final_status: string | null;
  approval_ids: number[];
  board_ids: number[];
  human_actions_needed: string[];
}

export interface RunInfo {
  run_id: string;
  ticket_id: number;
  status: "running" | "done" | "error";
  started_at: string;
  finished_at: string | null;
  error: string | null;
  resolved: boolean | null;
  result: { output: BossDecision; requests: number; total_tokens: number } | null;
}

export interface Approval {
  id: number;
  kind: "payment" | "purchase_order" | "discount";
  ticket_id: number | null;
  summary: string;
  amount: number;
  details: Record<string, unknown>;
  requested_by: AgentName;
  status: "pending" | "approved" | "rejected" | "executed";
  decided_by: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
  executed_at: string | null;
}

export interface Cash {
  account: string;
  balance: number;
  as_of: string;
  shop_date: string;
  open_invoices_total: number;
  rent_due_total: number;
  cash_after_commitments: number;
}

export interface BoardPost {
  id: number;
  ticket_id: number | null;
  author: string;
  kind: "draft" | "note";
  audience: "customer" | "vendor" | "landlord" | "internal";
  subject: string;
  body: string;
  created_at: string;
}

export interface Payment {
  id: number;
  kind: "invoice" | "lease";
  ref_id: number;
  amount: number;
  account: string;
  paid_at: string;
  approved_by: string;
}

export interface AgentSummary {
  agent: AgentName;
  asked_by: AgentName[];
  runs: number;
  tools: Record<string, number>;
  delegated_to: AgentName[];
  approval_ids: number[];
  board_ids: number[];
  summary: string | null;
  tokens: number;
  steps: number;
}

export interface TicketSummary {
  ticket_id: number;
  run_id: string | null;
  started_at?: string;
  last_at?: string;
  decision?: BossDecision | null; // the boss's final output, read from the audit trail
  agents: AgentSummary[];
}

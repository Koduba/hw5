// Thin client for the Problem 7 routes. The browser calls the FastAPI backend directly;
// the backend's CORS allows this page's origin (http://localhost:5173).
import type {
  Approval, BoardPost, Cash, EventsPage, Payment, RunInfo, Ticket, TicketSummary,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}. Is uvicorn running?`);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const d = body?.detail;
    const msg = typeof d === "string" ? d : d?.reason ?? (d ? JSON.stringify(d) : res.statusText);
    throw new ApiError(res.status, msg);
  }
  return body as T;
}

export const api = {
  tickets: () => request<Ticket[]>("/api/tickets"),
  runTicket: (id: number) => request<RunInfo>(`/api/tickets/${id}/run`, { method: "POST" }),
  runs: () => request<RunInfo[]>("/api/runs"),
  run: (runId: string) => request<RunInfo>(`/api/runs/${runId}`),
  events: (opts: { since?: number; limit?: number; runId?: string; ticketId?: number }) => {
    const q = new URLSearchParams();
    if (opts.since !== undefined) q.set("since", String(opts.since));
    if (opts.limit) q.set("limit", String(opts.limit));
    if (opts.runId) q.set("run_id", opts.runId);
    if (opts.ticketId !== undefined) q.set("ticket_id", String(opts.ticketId));
    return request<EventsPage>(`/api/events?${q}`);
  },
  summary: (ticketId: number) => request<TicketSummary>(`/api/tickets/${ticketId}/summary`),
  approvals: () => request<Approval[]>("/api/approvals"),
  approve: (id: number, approver: string) =>
    request<{ executed?: { balance_after?: number } }>(`/api/approvals/${id}/approve`, {
      method: "POST", body: JSON.stringify({ approver }),
    }),
  reject: (id: number, approver: string) =>
    request(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ approver }) }),
  cash: () => request<Cash>("/api/cash"),
  board: () => request<BoardPost[]>("/api/board"),
  payments: () => request<{ payments: Payment[]; total_paid: number }>("/api/payments"),
  resolve: (id: number, approver: string) =>
    request(`/api/tickets/${id}/resolve`, { method: "POST", body: JSON.stringify({ approver }) }),
  reset: () => request("/api/reset", { method: "POST" }),
};

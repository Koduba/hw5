import { TICKET_ICON } from "../agentMeta";
import type { Approval, RunInfo, Ticket } from "../types";

const STATUS_LABEL: Record<Ticket["status"], string> = {
  open: "Open",
  in_progress: "In progress",
  waiting_on_human: "Needs your OK",
  resolved: "Resolved",
};

interface Props {
  tickets: Ticket[];
  selected: number | null;
  onSelect: (id: number) => void;
  activeRun: RunInfo | null;
  approvals: Approval[];
}

function facts(t: Ticket): string {
  if (t.sku) return `${t.sku} · ${t.size} · ×${t.qty}`;
  if (t.lease_id) return `Lease #${t.lease_id}`;
  if (t.invoice_id) return `Invoice #${t.invoice_id}`;
  return t.type.replace(/_/g, " ");
}

export function TicketQueue({ tickets, selected, onSelect, activeRun, approvals }: Props) {
  const open = tickets.filter((t) => t.state === "open").length;
  return (
    <section className="panel queue" aria-label="Ticket queue">
      <div className="panel-head">
        <h2>Queue</h2>
        <span className="muted">{open} open · {tickets.length - open} resolved</span>
      </div>
      <ul className="ticket-list">
        {tickets.map((t) => {
          const running = activeRun?.status === "running" && activeRun.ticket_id === t.id;
          const pending = approvals.filter((a) => a.ticket_id === t.id && a.status === "pending").length;
          return (
            <li key={t.id}>
              <button
                className={`ticket-card ${selected === t.id ? "selected" : ""} ${t.state} ${running ? "running" : ""}`}
                onClick={() => onSelect(t.id)}
                aria-pressed={selected === t.id}
              >
                <div className="tc-top">
                  <span className="tc-icon" aria-hidden>{TICKET_ICON[t.type] ?? "•"}</span>
                  <span className="tc-id">#{t.id}</span>
                  <span className={`pill status-${t.status}`}>
                    {running ? "Agents working" : STATUS_LABEL[t.status]}
                  </span>
                </div>
                <div className="tc-subject">{t.subject}</div>
                <div className="tc-req">{t.requester}</div>
                <div className="tc-facts">{facts(t)}</div>
                {pending > 0 && <div className="tc-flag">{pending} approval{pending > 1 ? "s" : ""} waiting</div>}
                {running && <div className="tc-progress" aria-hidden />}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

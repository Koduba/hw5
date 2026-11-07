import type { RunInfo, Ticket } from "../types";

interface Props {
  shopDate: string | null;
  activeRun: RunInfo | null;
  tickets: Ticket[];
  approver: string;
  onApprover: (name: string) => void;
  onReset: () => void;
  online: boolean;
}

export function Header({ shopDate, activeRun, tickets, approver, onApprover, onReset, online }: Props) {
  const running = activeRun?.status === "running";
  const ticket = tickets.find((t) => t.id === activeRun?.ticket_id);
  return (
    <header className="topbar">
      <div className="brand">
        <div className="logo" aria-hidden>CC</div>
        <div>
          <div className="brand-name">Campus Customs</div>
          <div className="brand-sub">Operations Desk</div>
        </div>
      </div>

      <div className={`team-status ${running ? "live" : online ? "" : "offline"}`} role="status" aria-live="polite">
        <span className="dot" aria-hidden />
        {!online
          ? "Backend offline: start uvicorn on :8000"
          : running
            ? <>Team working on <strong>#{activeRun!.ticket_id}</strong>{ticket ? ` · ${ticket.subject}` : ""}</>
            : "Team idle · pick a ticket to start"}
      </div>

      <div className="topbar-right">
        {shopDate && (
          <div className="chip" title="desk.date_today: the shop's 'today'">
            <span className="chip-k">Shop date</span> {shopDate}
          </div>
        )}
        <label className="approver">
          <span>On desk</span>
          <input
            value={approver}
            onChange={(e) => onApprover(e.target.value)}
            placeholder="Your name"
            aria-label="Your name, recorded on approvals"
          />
        </label>
        <button className="btn ghost" onClick={onReset} disabled={running} title="Restore the working database from the original">
          ↺ Reset shop
        </button>
      </div>
    </header>
  );
}

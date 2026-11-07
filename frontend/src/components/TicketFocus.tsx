import { TICKET_ICON } from "../agentMeta";
import { useElapsed } from "../hooks";
import type { RunInfo, Ticket } from "../types";

interface Props {
  ticket: Ticket;
  run: RunInfo | null; // latest run for this ticket
  busy: boolean; // any run in progress (team is shared)
  onRun: () => void;
  pending: number; // approvals on this ticket still waiting
  approver: string;
  onResolve: () => void;
}

export function TicketFocus({ ticket, run, busy, onRun, pending, approver, onResolve }: Props) {
  const running = run?.status === "running";
  const secs = useElapsed(run?.started_at, running, run?.finished_at);
  const label = ticket.state === "resolved" ? "Run the team again" : run ? "Re-run the team" : "Run the agent team";

  return (
    <section className="focus" aria-label={`Ticket ${ticket.id}`}>
      <div className="focus-main">
        <div className="focus-kicker">
          <span aria-hidden>{TICKET_ICON[ticket.type] ?? "•"}</span> {ticket.type.replace(/_/g, " ")} · #{ticket.id} ·{" "}
          {new Date(ticket.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
        </div>
        <h1>{ticket.subject}</h1>
        <div className="focus-from">from <strong>{ticket.requester}</strong></div>
        {ticket.notes && <blockquote>“{ticket.notes}”</blockquote>}
      </div>

      <div className="focus-side">
        <button className="btn primary big" onClick={onRun} disabled={busy}>
          {running ? <><span className="spinner" aria-hidden /> Team is on it…</> : <>▶ {label}</>}
        </button>
        {run && (
          <div className={`run-meta ${run.status}`}>
            {run.status === "running" && <>Running · {secs}s</>}
            {run.status === "done" && (
              <>
                Finished in {secs}s · {run.result?.requests} calls · {(run.result?.total_tokens ?? 0).toLocaleString()} tokens
              </>
            )}
            {run.status === "error" && <>Run failed: {run.error}</>}
          </div>
        )}
        {busy && !running && <div className="run-meta">Another ticket is running. The team works one at a time.</div>}
      </div>

      {ticket.state === "resolved" && (
        <div className="outcome ok" role="status">✓ <strong>Resolved.</strong> Nothing on this ticket is waiting on a human.</div>
      )}
      {ticket.status === "waiting_on_human" && !busy && (
        pending > 0 ? (
          <div className="outcome wait" role="status">
            ⏳ <strong>Waiting on you.</strong> Decide the {pending} request{pending > 1 ? "s" : ""} on the right. The ticket resolves when the last one is decided.
          </div>
        ) : (
          <div className="outcome wait with-action" role="status">
            <span>⏳ <strong>The boss left this decision to you.</strong> Nothing needs approving. Read the decision and the draft, then close it.</span>
            <button className="btn primary" onClick={onResolve} disabled={!approver.trim()}
              title={approver.trim() ? "Recorded under your name" : "Type your name in On desk first"}>
              ✓ Mark resolved
            </button>
          </div>
        )
      )}
    </section>
  );
}

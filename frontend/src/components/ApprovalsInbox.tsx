import { useState } from "react";
import { agentLabel, money } from "../agentMeta";
import type { Approval, Cash } from "../types";

const KIND = {
  payment: { label: "Payment", icon: "💸", verb: "Approve & pay" },
  purchase_order: { label: "Purchase order", icon: "📦", verb: "Approve & place PO" },
  discount: { label: "Discount", icon: "🏷️", verb: "Approve price" },
} as const;

interface Props {
  approvals: Approval[];
  cash: Cash | null;
  approver: string;
  onDecide: (a: Approval, decision: "approve" | "reject") => Promise<void>;
}

export function ApprovalsInbox({ approvals, cash, approver, onDecide }: Props) {
  const [busy, setBusy] = useState<number | null>(null);
  const pending = approvals.filter((a) => a.status === "pending");
  const decided = approvals.filter((a) => a.status !== "pending").slice(-4).reverse();

  const decide = async (a: Approval, d: "approve" | "reject") => {
    setBusy(a.id);
    try {
      await onDecide(a, d);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className={`panel inbox ${pending.length ? "has-pending" : ""}`} aria-label="Approvals">
      <div className="panel-head">
        <h2>Needs your OK {pending.length > 0 && <span className="count">{pending.length}</span>}</h2>
        <span className="muted">agents request · you decide</span>
      </div>
      {!approver.trim() && pending.length > 0 && (
        <div className="hint">Type your name in <strong>On desk</strong> (top right). It's recorded as the approver.</div>
      )}
      {pending.length === 0 && <div className="empty-feed small">Nothing waiting. Payments, POs and discounts the agents file will land here.</div>}
      <ul className="approval-list">
        {pending.map((a) => {
          const k = KIND[a.kind];
          const d = a.details as Record<string, unknown>;
          const after = a.kind === "payment" && cash ? cash.balance - a.amount : null;
          const blocked = a.kind === "purchase_order" && Array.isArray(d.blocked_by_open_invoices) && d.blocked_by_open_invoices.length > 0;
          return (
            <li key={a.id} className={`approval k-${a.kind}`}>
              <div className="ap-top">
                <span className="ap-icon" aria-hidden>{k.icon}</span>
                <span className="ap-kind">{k.label} #{a.id}</span>
                {a.ticket_id && <span className="tag">ticket #{a.ticket_id}</span>}
                <span className="ap-amt">{a.kind === "discount" ? `${money(a.amount)} off list` : money(a.amount)}</span>
              </div>
              <p className="ap-sum">{a.summary}</p>
              <div className="ap-meta">
                requested by <strong>{agentLabel(a.requested_by)}</strong>
                {typeof d.reason === "string" && <> · “{d.reason}”</>}
              </div>
              {after !== null && (
                <div className={`ap-after ${after < 0 ? "bad" : ""}`}>
                  Checking after: <strong>{money(after)}</strong>{after < 0 && " (the pay tool will refuse this)"}
                </div>
              )}
              {blocked && <div className="ap-after bad">Vendor is blocked by an open invoice. Placing will be refused until it's paid.</div>}
              <div className="ap-actions">
                <button className="btn primary" disabled={!approver.trim() || busy !== null} onClick={() => decide(a, "approve")}>
                  {busy === a.id ? "Working…" : k.verb}
                </button>
                <button className="btn ghost" disabled={!approver.trim() || busy !== null} onClick={() => decide(a, "reject")}>
                  Reject
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      {decided.length > 0 && (
        <ul className="decided">
          {decided.map((a) => (
            <li key={a.id}>
              <span className={`pill st-${a.status}`}>{a.status}</span>
              <span className="truncate">{KIND[a.kind].label} #{a.id} · {money(a.amount)}</span>
              <span className="muted">{a.decided_by}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

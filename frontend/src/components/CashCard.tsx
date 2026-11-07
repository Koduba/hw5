import { useEffect, useRef, useState } from "react";
import { money } from "../agentMeta";
import { useAnimatedNumber } from "../hooks";
import type { Cash, Payment } from "../types";

export function CashCard({ cash, payments }: { cash: Cash | null; payments: Payment[] }) {
  const balance = cash?.balance ?? 0;
  const shown = useAnimatedNumber(balance);
  const prev = useRef<number | null>(null);
  const [delta, setDelta] = useState<number | null>(null);

  useEffect(() => {
    if (cash == null) return;
    if (prev.current !== null && balance !== prev.current) {
      setDelta(balance - prev.current);
      const t = window.setTimeout(() => setDelta(null), 6000);
      prev.current = balance;
      return () => window.clearTimeout(t);
    }
    prev.current = balance;
  }, [balance, cash]);

  const paid = payments.reduce((s, p) => s + p.amount, 0);
  const start = balance + paid;
  const owed = (cash?.open_invoices_total ?? 0) + (cash?.rent_due_total ?? 0);
  const pct = (n: number) => `${Math.max(0, Math.min(100, (n / Math.max(start, 1)) * 100))}%`;

  return (
    <section className="panel cash" aria-label="Checking balance">
      <div className="panel-head">
        <h2>Checking</h2>
        <span className="muted">cash_accounts · as of {cash?.as_of ?? "—"}</span>
      </div>
      <div className={`cash-big ${delta && delta < 0 ? "dropped" : ""}`} aria-live="polite">
        {money(shown)}
        {delta !== null && <span className={`delta ${delta < 0 ? "down" : "up"}`}>{delta < 0 ? "−" : "+"}{money(Math.abs(delta))}</span>}
      </div>
      <div className="cash-bar" role="img" aria-label={`Balance ${money(balance)}, owed ${money(owed)}`}>
        <span className="seg paid" style={{ width: pct(paid) }} title={`Paid out ${money(paid)}`} />
        <span className="seg owed" style={{ width: pct(Math.min(owed, balance)) }} title={`Owed ${money(owed)}`} />
        <span className="seg free" style={{ width: pct(Math.max(0, balance - owed)) }} title="Free after commitments" />
      </div>
      <dl className="cash-lines">
        <div><dt><i className="sw paid" />Paid out</dt><dd>{money(paid)}</dd></div>
        <div><dt><i className="sw owed" />Still owed (invoices + rent)</dt><dd>{money(owed)}</dd></div>
        <div className="strong"><dt><i className="sw free" />Free after commitments</dt><dd>{money(cash?.cash_after_commitments)}</dd></div>
      </dl>
      {payments.length > 0 && (
        <ul className="ledger">
          {payments.map((p) => (
            <li key={p.id}>
              <span>{p.kind === "lease" ? "Rent · lease" : "Invoice"} #{p.ref_id}</span>
              <span className="muted">by {p.approved_by}</span>
              <strong>−{money(p.amount)}</strong>
            </li>
          ))}
        </ul>
      )}
      <p className="fine">Cash only moves when a person approves a payment. Money only goes out in this shop model.</p>
    </section>
  );
}

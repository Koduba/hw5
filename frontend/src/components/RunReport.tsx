import { AGENT_META, agentLabel, toolVerb } from "../agentMeta";
import type { RunInfo, TicketSummary } from "../types";

export function RunReport({ summary, run }: { summary: TicketSummary | null; run: RunInfo | null }) {
  if (!summary || !summary.agents.length) {
    return <div className="empty-feed">The report appears here after the team has worked this ticket.</div>;
  }
  const decision = run?.result?.output ?? summary.decision ?? undefined;
  return (
    <div className="report">
      {decision && (
        <div className="decision">
          <div className="decision-k">Boss's decision</div>
          <p>{decision.decision}</p>
          {decision.human_actions_needed.length > 0 && (
            <>
              <div className="decision-k">What you need to do</div>
              <ul>{decision.human_actions_needed.map((h, i) => <li key={i}>{h}</li>)}</ul>
            </>
          )}
        </div>
      )}
      <div className="report-grid">
        {summary.agents.map((a) => {
          const meta = AGENT_META[a.agent];
          const tools = Object.entries(a.tools);
          return (
            <article key={a.agent} className="report-card" style={{ "--agent": meta.color } as React.CSSProperties}>
              <header>
                <span className="avatar sm" aria-hidden>{meta.icon}</span>
                <strong>{meta.label}</strong>
                {a.asked_by.length > 0 && <span className="muted">asked by {a.asked_by.map(agentLabel).join(", ")}</span>}
                {a.runs > 1 && <span className="tag warn" title="This agent was called more than once on this run">called ×{a.runs}</span>}
              </header>
              <p>{a.summary ?? "No final report."}</p>
              <div className="report-tags">
                {tools.map(([t, n]) => (
                  <span key={t} className="tag tool" title={toolVerb(t)}>{t}{n > 1 ? ` ×${n}` : ""}</span>
                ))}
                {a.delegated_to.map((d, i) => <span key={i} className="tag">→ {agentLabel(d)}</span>)}
                {a.approval_ids.map((id) => <span key={id} className="tag pink">approval #{id}</span>)}
                {a.board_ids.map((id) => <span key={id} className="tag">draft #{id}</span>)}
              </div>
              <div className="report-foot">{a.tokens.toLocaleString()} tokens · {a.steps} steps</div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

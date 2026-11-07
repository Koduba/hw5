import { useState } from "react";
import { agentLabel } from "../agentMeta";
import type { BoardPost } from "../types";

const AUDIENCE_ICON = { customer: "🧑‍🎓", landlord: "🏢", vendor: "🏭", internal: "📝" } as const;

export function BoardDrafts({ posts, ticketId }: { posts: BoardPost[]; ticketId: number | null }) {
  const [open, setOpen] = useState<number | null>(null);
  const drafts = posts.filter((p) => p.kind === "draft" && (ticketId === null || p.ticket_id === ticketId));
  return (
    <section className="panel drafts" aria-label="Draft messages">
      <div className="panel-head">
        <h2>Drafts</h2>
        <span className="muted">{ticketId ? `ticket #${ticketId}` : "all tickets"} · never sent</span>
      </div>
      {drafts.length === 0 && <div className="empty-feed small">No drafts yet. Customer, landlord and vendor messages appear here for review.</div>}
      <ul className="draft-list">
        {drafts.map((p) => (
          <li key={p.id} className={`draft ${open === p.id ? "open" : ""}`}>
            <button className="draft-head" onClick={() => setOpen(open === p.id ? null : p.id)} aria-expanded={open === p.id}>
              <span aria-hidden>{AUDIENCE_ICON[p.audience]}</span>
              <span className="truncate"><strong>{p.subject}</strong></span>
              <span className="stamp">DRAFT</span>
            </button>
            <div className="draft-meta">to {p.audience} · by {agentLabel(p.author)} · #{p.id}</div>
            {open === p.id && <pre className="draft-body">{p.body}</pre>}
          </li>
        ))}
      </ul>
    </section>
  );
}

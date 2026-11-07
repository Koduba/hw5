import { useEffect, useRef } from "react";
import { AGENT_META, argsBrief, readable, timeOf, toolVerb } from "../agentMeta";
import type { AgentEvent } from "../types";

const SHOWN = new Set(["start", "tool_call", "delegate", "delegate_reply", "refused", "finish", "error"]);

function line(e: AgentEvent): { text: string; detail?: string } {
  switch (e.kind) {
    case "start":
      return { text: e.depth === 0 ? "Started on the ticket" : "Picked up a request", detail: e.said ?? undefined };
    case "tool_call":
      return { text: toolVerb(e.tool), detail: argsBrief(e.args) };
    case "delegate":
    case "delegate_reply":
    case "finish":
      return { text: readable(e.said) ?? "" };
    default:
      return { text: e.said ?? e.kind };
  }
}

export function LiveFeed({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const shown = events.filter((e) => SHOWN.has(e.kind));
  const list = useRef<HTMLOListElement>(null);
  useEffect(() => {
    // Follow new steps inside the feed only; never scroll the whole page.
    const el = list.current;
    if (running && el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [shown.length, running]);

  if (!shown.length) {
    return <div className="empty-feed">No activity yet. Start the team and every step will stream in here.</div>;
  }
  return (
    <ol className="feed" ref={list} aria-live="polite" aria-relevant="additions">
      {shown.map((e) => {
        const meta = AGENT_META[e.agent];
        const { text, detail } = line(e);
        return (
          <li key={e.index} className={`feed-item k-${e.kind}`} style={{ "--agent": meta.color, "--depth": e.depth } as React.CSSProperties}>
            <span className="feed-time">{timeOf(e.at)}</span>
            <span className="feed-dot" aria-hidden>{meta.icon}</span>
            <div className="feed-body">
              <span className="feed-agent">{meta.label}</span>
              {e.kind === "tool_call" && <code className="feed-tool">{e.tool}</code>}
              {e.kind === "delegate" && <code className="feed-tool">ask_teammate</code>}
              <div className="feed-text">{text}</div>
              {detail && <div className="feed-detail">{detail}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

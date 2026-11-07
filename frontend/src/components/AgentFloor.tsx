import { AGENT_META, agentLabel, stations, toolVerb } from "../agentMeta";
import { AGENTS, type AgentEvent, type AgentName } from "../types";

const STATE_LABEL = {
  idle: "Off this ticket",
  thinking: "Thinking",
  working: "Using a tool",
  delegating: "Waiting on a teammate",
  waiting: "Waiting",
  done: "Done",
  error: "Error",
} as const;

interface Props {
  events: AgentEvent[];
  running: boolean;
  hasRun: boolean;
}

export function AgentFloor({ events, running, hasRun }: Props) {
  const st = stations(events);
  // Delegation links seen in this run, e.g. boss→facilities, facilities→accounting.
  const links = Array.from(
    new Set(events.filter((e) => e.kind === "delegate").map((e) => `${e.agent}→${(e.said ?? "").match(/^→ ?([a-z_]+)/)?.[1] ?? "?"}`)),
  );

  const card = (a: AgentName) => {
    const s = st[a];
    const meta = AGENT_META[a];
    const active = running && (s.state === "working" || s.state === "thinking");
    const stateLabel = s.state === "idle" && !hasRun ? "Standing by" : STATE_LABEL[s.state];
    return (
      <article
        key={a}
        className={`station ${s.state} ${active ? "active" : ""} ${a === "boss" ? "boss" : ""}`}
        style={{ "--agent": meta.color } as React.CSSProperties}
        aria-label={`${meta.label}: ${stateLabel}`}
      >
        <div className="st-head">
          <div className="avatar" aria-hidden>{meta.icon}</div>
          <div className="st-who">
            <div className="st-name">{meta.label}</div>
            <div className="st-role">{meta.role}</div>
          </div>
          <span className={`st-state s-${s.state}`}>{stateLabel}</span>
        </div>
        <div className="bubble" aria-live={active ? "polite" : "off"}>
          {s.line ? s.line : <span className="muted">{hasRun ? "Not needed on this ticket." : "Waiting for a run."}</span>}
        </div>
        <div className="st-foot">
          {s.askedBy && <span className="tag">asked by {agentLabel(s.askedBy)}</span>}
          {s.tool && s.state !== "done" && <span className="tag tool">{toolVerb(s.tool)}</span>}
          {s.tools > 0 && <span className="tag">{s.tools} tool call{s.tools > 1 ? "s" : ""}</span>}
        </div>
      </article>
    );
  };

  return (
    <section className="panel floor" aria-label="Agent floor">
      <div className="panel-head">
        <h2>Agent floor</h2>
        <span className="muted">
          {links.length ? <>Hand-offs: {links.map((l) => l.split("→").map(agentLabel).join(" → ")).join(" · ")}</> : "Who's doing what, live"}
        </span>
      </div>
      <div className="floor-boss">{card("boss")}</div>
      <div className="floor-grid">{AGENTS.filter((a) => a !== "boss").map(card)}</div>
    </section>
  );
}

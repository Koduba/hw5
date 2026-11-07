import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { money } from "./agentMeta";
import { usePolling } from "./hooks";
import type { AgentEvent, Approval, BoardPost, Cash, Payment, RunInfo, Ticket, TicketSummary } from "./types";
import { Header } from "./components/Header";
import { TicketQueue } from "./components/TicketQueue";
import { TicketFocus } from "./components/TicketFocus";
import { AgentFloor } from "./components/AgentFloor";
import { LiveFeed } from "./components/LiveFeed";
import { RunReport } from "./components/RunReport";
import { CashCard } from "./components/CashCard";
import { ApprovalsInbox } from "./components/ApprovalsInbox";
import { BoardDrafts } from "./components/BoardDrafts";

type Toast = { kind: "ok" | "err" | "info"; text: string } | null;

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [board, setBoard] = useState<BoardPost[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [online, setOnline] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [summary, setSummary] = useState<TicketSummary | null>(null);
  const [tab, setTab] = useState<"feed" | "report">("feed");
  const [toast, setToast] = useState<Toast>(null);
  const [approver, setApprover] = useState(() => localStorage.getItem("cc-approver") ?? "");
  const cursor = useRef<number | undefined>(undefined);
  const eventsRun = useRef<string | null>(null);

  useEffect(() => localStorage.setItem("cc-approver", approver), [approver]);
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const fail = (e: unknown) => setToast({ kind: "err", text: e instanceof Error ? e.message : String(e) });

  // ---- shop state (every 3 s) -------------------------------------------------
  const refreshShop = useCallback(async () => {
    try {
      const [t, a, c, b, p, r] = await Promise.all([
        api.tickets(), api.approvals(), api.cash(), api.board(), api.payments(), api.runs(),
      ]);
      setTickets(t); setApprovals(a); setCash(c); setBoard(b); setPayments(p.payments); setRuns(r);
      setOnline(true);
      setSelected((s) => s ?? t.find((x) => x.state === "open")?.id ?? t[0]?.id ?? null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 0) setOnline(false);
    }
  }, []);
  usePolling(refreshShop, 3000);

  const activeRun = runs.find((r) => r.status === "running") ?? null;
  const ticketRun = runs.find((r) => r.ticket_id === selected) ?? null; // newest first
  const runningHere = ticketRun?.status === "running";

  // ---- events for the selected ticket's latest run ----------------------------
  const loadTicketEvents = useCallback(async (id: number) => {
    const page = await api.events({ ticketId: id, limit: 500 });
    const last = page.events.at(-1)?.run_id ?? null;
    eventsRun.current = last;
    setEvents(page.events.filter((e) => e.run_id === last));
    cursor.current = page.next;
    setSummary(await api.summary(id));
  }, []);

  useEffect(() => {
    if (selected == null) return;
    setTab("feed");
    loadTicketEvents(selected).catch(fail);
  }, [selected, loadTicketEvents]);

  // While this ticket's run is going, stream new steps every 1.2 s.
  usePolling(async () => {
    if (!ticketRun) return;
    const page = await api.events({ since: cursor.current, runId: ticketRun.run_id, limit: 500 });
    cursor.current = page.next;
    if (page.events.length) {
      if (eventsRun.current !== ticketRun.run_id) {
        eventsRun.current = ticketRun.run_id;
        setEvents(page.events);
      } else {
        setEvents((prev) => [...prev, ...page.events.filter((e) => !prev.some((p) => p.index === e.index))]);
      }
    }
  }, 1200, runningHere);

  // When a run finishes: refresh, load the report, tell the human what happened.
  const wasRunning = useRef<string | null>(null);
  useEffect(() => {
    if (runningHere) {
      wasRunning.current = ticketRun!.run_id;
      return;
    }
    if (ticketRun && wasRunning.current === ticketRun.run_id) {
      wasRunning.current = null;
      refreshShop();
      loadTicketEvents(ticketRun.ticket_id).then(() => setTab("report")).catch(fail);
      if (ticketRun.status === "error") setToast({ kind: "err", text: `Run failed: ${ticketRun.error}` });
      else if (ticketRun.resolved) setToast({ kind: "ok", text: `Ticket #${ticketRun.ticket_id} resolved.` });
      else setToast({ kind: "info", text: `Ticket #${ticketRun.ticket_id} is waiting on your approval.` });
    }
  }, [runningHere, ticketRun, refreshShop, loadTicketEvents]);

  // ---- actions ---------------------------------------------------------------
  const runTeam = async () => {
    if (selected == null) return;
    try {
      const head = await api.events({ limit: 1 });
      cursor.current = head.next;
      const r = await api.runTicket(selected);
      eventsRun.current = r.run_id;
      setEvents([]);
      setSummary(null);
      setTab("feed");
      setRuns((prev) => [r, ...prev]);
    } catch (e) {
      fail(e);
    }
  };

  const decide = async (a: Approval, d: "approve" | "reject") => {
    try {
      const before = cash?.balance ?? 0;
      const out = d === "approve" ? await api.approve(a.id, approver.trim()) : await api.reject(a.id, approver.trim());
      const after = (out as { executed?: { balance_after?: number } }).executed?.balance_after;
      setToast({
        kind: "ok",
        text: d === "reject"
          ? `Rejected #${a.id}. Nothing moved.`
          : after !== undefined
            ? `Paid ${money(a.amount)} · checking ${money(before)} → ${money(after)}`
            : `Approved #${a.id}.`,
      });
    } catch (e) {
      fail(e);
    }
    await refreshShop();
    if (selected != null) setSummary(await api.summary(selected).catch(() => null));
  };

  const resolveTicket = async () => {
    if (selected == null) return;
    try {
      await api.resolve(selected, approver.trim());
      setToast({ kind: "ok", text: `Ticket #${selected} resolved by ${approver.trim()}.` });
    } catch (e) {
      fail(e);
    }
    await refreshShop();
  };

  const reset = async () => {
    if (!window.confirm("Reset the shop database to the original values? Approvals, payments and drafts are cleared. The audit trail is kept.")) return;
    try {
      await api.reset();
      setToast({ kind: "ok", text: "Shop reset to the original database." });
      await refreshShop();
    } catch (e) {
      fail(e);
    }
  };

  const ticket = tickets.find((t) => t.id === selected) ?? null;
  const shopDate = cash?.shop_date ?? null;

  return (
    <div className="app">
      <Header shopDate={shopDate} activeRun={activeRun} tickets={tickets} approver={approver}
        onApprover={setApprover} onReset={reset} online={online} />

      <main className="desk">
        <aside className="col-left">
          <TicketQueue tickets={tickets} selected={selected} onSelect={setSelected} activeRun={activeRun} approvals={approvals} />
        </aside>

        <div className="col-center">
          {ticket ? (
            <>
              <TicketFocus ticket={ticket} run={ticketRun} busy={!!activeRun} onRun={runTeam} approver={approver}
                pending={approvals.filter((a) => a.ticket_id === ticket.id && a.status === "pending").length}
                onResolve={resolveTicket} />
              <AgentFloor events={events} running={runningHere} hasRun={events.length > 0} />
              <section className="panel stream">
                <div className="tabs" role="tablist" aria-label="Run detail">
                  <button role="tab" aria-selected={tab === "feed"} className={tab === "feed" ? "on" : ""} onClick={() => setTab("feed")}>
                    Live feed {runningHere && <span className="live-dot" aria-hidden />}
                  </button>
                  <button role="tab" aria-selected={tab === "report"} className={tab === "report" ? "on" : ""} onClick={() => setTab("report")}>
                    What each agent did
                  </button>
                  {summary?.run_id && <span className="muted tab-meta">run {summary.run_id}</span>}
                </div>
                <div role="tabpanel">
                  {tab === "feed" ? <LiveFeed events={events} running={runningHere} /> : <RunReport summary={summary} run={ticketRun} />}
                </div>
              </section>
            </>
          ) : (
            <div className="panel empty-feed">{online ? "Loading tickets…" : "Start the backend: cd backend && uvicorn main:app --reload --port 8000"}</div>
          )}
        </div>

        <aside className="col-right">
          <CashCard cash={cash} payments={payments} />
          <ApprovalsInbox approvals={approvals} cash={cash} approver={approver} onDecide={decide} />
          <BoardDrafts posts={board} ticketId={selected} />
        </aside>
      </main>

      {toast && <div className={`toast ${toast.kind}`} role="status">{toast.text}</div>}
    </div>
  );
}

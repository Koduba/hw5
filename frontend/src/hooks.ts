import { useEffect, useRef, useState } from "react";

/** Call `fn` now and every `ms` while `enabled`. Keeps the latest fn without restarting the timer. */
export function usePolling(fn: () => void | Promise<void>, ms: number, enabled = true) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    let timer: number;
    const tick = async () => {
      try {
        await ref.current();
      } finally {
        if (alive) timer = window.setTimeout(tick, ms);
      }
    };
    tick();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [ms, enabled]);
}

/** Tween a number toward its new value (used for the cash balance). */
export function useAnimatedNumber(target: number, duration = 1200): number {
  const [value, setValue] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const step = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(a + (target - a) * eased);
      if (p < 1) raf = requestAnimationFrame(step);
      else from.current = target;
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      from.current = target;
    };
  }, [target, duration]);
  return value;
}

/** Seconds since `iso`, ticking every second while `active`. */
export function useElapsed(iso: string | null | undefined, active: boolean, endIso?: string | null): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [active]);
  if (!iso) return 0;
  const end = endIso ? new Date(endIso).getTime() : now;
  return Math.max(0, Math.round((end - new Date(iso).getTime()) / 1000));
}

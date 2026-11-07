import type { Alert, FcKey, Payload, Period } from "@/data/types";
import { Q_MS } from "./time";

export const STEPS = 40;
export let PAYLOAD: Payload;
export let PERIOD_IDS: string[] = [];

/** the data: inlined in bundle.html (<script id="payload" type="application/json">), else public/payload.json */
export async function loadPayload(): Promise<void> {
  const el = document.getElementById("payload");
  const p: Payload = el?.textContent ? JSON.parse(el.textContent) : await (await fetch("payload.json")).json();
  PAYLOAD = p;
  PERIOD_IDS = ["val", "test"].filter((k) => k in p.periods);
}

export const qMs = (p: Period, gi: number) => p.t0 + gi * Q_MS;
/** review time of forecast hour i, in minutes from t0 (the forecast origin) */
export const reviewMin = (p: Period, i: number) => p.origins[i] * 15;
export const reviewMs = (p: Period, i: number) => qMs(p, p.origins[i]);

/** a value of a published series, only if it was published by minute T */
export function known(vals: (number | null)[], fu: (number | null)[], gi: number, T: number): number | null {
  const f = fu[gi];
  const v = vals[gi];
  return f !== null && f !== undefined && f <= T && v !== null && v !== undefined ? v : null;
}

export function fc(p: Period, i: number, key: FcKey): number[] {
  return p.fc[key].slice(i * STEPS, (i + 1) * STEPS);
}

export interface Forecast {
  p10: number[]; p50: number[]; p90: number[]; pu: number[]; pd: number[]; pn: number[]; hi: number[]; lo: number[];
  frP50: number[]; ouP50: number[];
}

export function forecastAt(p: Period, i: number): Forecast {
  return {
    p10: fc(p, i, "p10"), p50: fc(p, i, "p50"), p90: fc(p, i, "p90"),
    pu: fc(p, i, "pu"), pd: fc(p, i, "pd"), pn: fc(p, i, "pn"),
    hi: fc(p, i, "hi"), lo: fc(p, i, "lo"),
    frP50: fc(p, i, "fr_p50"), ouP50: fc(p, i, "ou_p50"),
  };
}

export function driverTokens(p: Period, i: number, s: number): string[] {
  const c = p.driver_combos[p.drivers[i * STEPS + s]] ?? "";
  return c ? c.split(";") : [];
}

/** the most frequent drivers over steps a..b; "spot" (present almost everywhere) only when little else is named */
export function windowDrivers(p: Period, i: number, a: number, b: number, k = 3): string[] {
  const count = new Map<string, number>();
  for (let s = a; s <= b; s++) {
    driverTokens(p, i, s).forEach((d, rank) => count.set(d, (count.get(d) ?? 0) + (3 - Math.min(rank, 2))));
  }
  const ranked = [...count.entries()].sort((x, y) => y[1] - x[1]).map(([d]) => d);
  const rest = ranked.filter((d) => d !== "spot");
  return (rest.length >= k ? rest : ranked).slice(0, k);
}

/** last quarter whose imbalance price was published by the review time of hour i */
export function lastPublished(p: Period, i: number): number | null {
  const T = reviewMin(p, i);
  for (let gi = p.origins[i]; gi >= Math.max(0, p.origins[i] - 24); gi--) {
    if (known(p.imb, p.imb_fu, gi, T) !== null) return gi;
  }
  return null;
}

export const ALERT_ORDER: Record<Alert["level"], number> = { high: 0, medium: 1, info: 2 };

export function sortedAlerts(p: Period, i: number): Alert[] {
  return [...p.alerts[i]].sort((x, y) => ALERT_ORDER[x.level] - ALERT_ORDER[y.level] || x.a - y.a);
}

/** per forecast hour: how much is worth checking (high = 2, watch = 1), for the timeline */
export function alertWeights(p: Period): number[] {
  return p.alerts.map((al) => al.reduce((s, a) => s + (a.level === "high" ? 2 : a.level === "medium" ? 1 : 0.5), 0));
}

export interface Hindsight {
  n: number; mae: number; maeSpot: number; coverage: number; highN: number; highK: number; dirN: number; dirOk: number;
  series: { t: number; y: number; p10: number; p50: number; p90: number }[];
}

/**
 * Score the forecasts made in the `hours` before review hour i (all if hours is null), using only prices
 * published by the review time. `series`: each published quarter against the forecast made one hour before it.
 */
export function hindsight(p: Period, i: number, hours: number | null): Hindsight {
  const T = reviewMin(p, i);
  const from = hours === null ? 0 : Math.max(0, i - hours);
  let n = 0, ae = 0, aeSpot = 0, inside = 0, highN = 0, highK = 0, dirN = 0, dirOk = 0;
  for (let j = from; j <= i; j++) {
    for (let s = 0; s < STEPS; s++) {
      const gi = p.origins[j] + s;
      const y = known(p.imb, p.imb_fu, gi, T);
      if (y === null) continue;
      const r = j * STEPS + s;
      const sp = p.spot[gi];
      n++;
      ae += Math.abs(y - p.fc.p50[r]);
      if (sp !== null) aeSpot += Math.abs(y - sp);
      if (y >= p.fc.p10[r] && y <= p.fc.p90[r]) inside++;
      if (sp !== null && y > sp + 50) { highN++; if (p.fc.hi[r] >= 0.4) highK++; }
      const d = known(p.dir, p.dir_fu, gi, T);
      if (d !== null) {
        const pu = p.fc.pu[r], pd = p.fc.pd[r], pn = p.fc.pn[r];
        const guess = pu >= pd && pu >= pn ? 1 : pd >= pn ? -1 : 0;
        dirN++; if (guess === d) dirOk++;
      }
    }
  }
  // the forecast made one hour before each published quarter (steps 5-8)
  const series: Hindsight["series"] = [];
  const startGi = hours === null ? p.origins[0] : Math.max(p.origins[0], p.origins[i] - hours * 4);
  const byGi = new Map<number, number>();
  p.origins.forEach((g, j) => byGi.set(g, j));
  for (let gi = startGi; gi <= p.origins[i]; gi++) {
    const y = known(p.imb, p.imb_fu, gi, T);
    if (y === null) continue;
    const k = gi - 4;
    const ogi = k - ((((k - p.origins[0]) % 4) + 4) % 4);
    const j = byGi.get(ogi);
    if (j === undefined) continue;
    const r = j * STEPS + (gi - ogi);
    series.push({ t: qMs(p, gi), y, p10: p.fc.p10[r], p50: p.fc.p50[r], p90: p.fc.p90[r] });
  }
  return { n, mae: n ? ae / n : NaN, maeSpot: n ? aeSpot / n : NaN, coverage: n ? inside / n : NaN, highN, highK, dirN, dirOk, series };
}

/** default review hour: the first hour with a high-level item after a week of history */
export function defaultHour(p: Period): number {
  for (let i = Math.min(7 * 24, p.origins.length - 1); i < p.origins.length; i++) {
    if (p.alerts[i].some((a) => a.level === "high")) return i;
  }
  return Math.min(7 * 24, p.origins.length - 1);
}

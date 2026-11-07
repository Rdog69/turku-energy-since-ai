import { useEffect, useId, useMemo, useRef, useState } from "react";
import { scaleLinear } from "d3-scale";
import { area, curveMonotoneX, curveStepAfter, line } from "d3-shape";
import { Maximize2, MousePointerClick, Move, ZoomIn, ZoomOut } from "lucide-react";
import type { Alert, Period } from "@/data/types";
import { STEPS, forecastAt, known, qMs, reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { Q_MS, dateShort, hhmm, hourOf, type Lang } from "@/lib/time";
import { tickStep } from "@/lib/useZoom";
import { useSmoothRange } from "@/lib/useSmooth";

const H_MS = 3600_000;
export const H = H_MS;
export const BACK = 0.375; // share of the window left of "now"
const M = { l: 134, r: 96, t: 70 };   // top margin holds the hover card, so it never covers the data
const PLOT_H = 244, DIR_GAP = 24, DIR_H = 24, RISK_GAP = 30, RISK_HALF = 30, AXIS_H = 36;
const HI_THR = 0.4, LO_THR = 0.5; // the alert thresholds for high- and low-price risk

const fmt0 = (v: number) => Math.round(v).toLocaleString("en-US").replace(/,/g, " ");
const pct = (v: number) => `${Math.round(v * 100)} %`;
const grow = (origin: "top" | "bottom", v: number): React.CSSProperties => ({
  transform: `scaleY(${Math.max(0, Math.min(1, v))})`, transformOrigin: origin, transformBox: "fill-box",
  transition: "transform 260ms cubic-bezier(.2,.7,.2,1)",
});

/**
 * Price, balancing direction and spike risk on ONE time axis. Scrolling, dragging or the strip move through time:
 * "now" travels with the view, so nothing published after it is ever shown. Left of now: what was known.
 * Right: the forecast made at now. The window and the price axis glide instead of jumping.
 */
export function TimeChart({ p, i, tNow, win, lang, focus, zones, onPan, onZoom, onResetZoom, span, onQuarter }: {
  p: Period; i: number; tNow: number; win: [number, number]; lang: Lang; focus: Alert | null; zones: boolean;
  onPan: (ms: number) => void; onZoom: (factor: number) => void; onResetZoom: () => void;
  span: number; onQuarter: (s: number) => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [W, setW] = useState(1000);
  const [hover, setHover] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const uid = useId().replace(/:/g, "");

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(680, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const [d0, d1] = win;
  const x = useMemo(() => scaleLinear().domain([d0, d1]).range([M.l, W - M.r]), [d0, d1, W]);
  const msPerPx = (d1 - d0) / (W - M.l - M.r);

  // wheel: scroll moves through time (either direction); ctrl/cmd + wheel or a pinch zooms
  const cb = useRef({ onPan, onZoom, msPerPx });
  cb.current = { onPan, onZoom, msPerPx };
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const c = cb.current;
      if (e.ctrlKey || e.metaKey) { c.onZoom(Math.exp(e.deltaY * 0.01)); return; }
      const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      c.onPan(d * c.msPerPx);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // "now" can sit between forecast hours (15-minute steps); the forecast shown is the latest made by then
  const T = tNow;
  const Tmin = Math.round((T - p.t0) / 60_000);
  const o = p.origins[i];
  const q0 = Math.max(0, Math.min(3, Math.round((T - reviewMs(p, i)) / Q_MS)));
  const madeAt = reviewMs(p, i);
  const F = useMemo(() => forecastAt(p, i), [p, i]);
  // the forecast made an hour earlier, for the same quarter-hours (dynamics: did the risk rise or fall?)
  const prev = useMemo(() => (i > 0 && p.origins[i - 1] === o - 4 ? forecastAt(p, i - 1) : null), [p, i, o]);
  const prevAt = (arr: "hi" | "lo", s: number) => (prev && s + 4 < STEPS ? prev[arr][s + 4] : null);
  const horizonEnd = qMs(p, o + STEPS);

  const g0 = Math.max(0, Math.floor((d0 - p.t0) / Q_MS) - 1);
  const g1 = Math.min(p.nq - 1, Math.ceil((d1 - p.t0) / Q_MS) + 1);
  const past = useMemo(() => {
    const out: { gi: number; t: number; y: number | null; spot: number | null; dir: number | null }[] = [];
    for (let gi = g0; gi <= g1; gi++) {
      out.push({
        gi, t: qMs(p, gi),
        y: gi < o + q0 ? known(p.imb, p.imb_fu, gi, Tmin) : null,
        spot: known(p.spot, p.spot_fu, gi, Tmin),
        dir: gi < o + q0 ? known(p.dir, p.dir_fu, gi, Tmin) : null,
      });
    }
    return out;
  }, [p, g0, g1, o, q0, Tmin]);
  const fut = useMemo(() => F.p50.map((_, s) => ({ t: qMs(p, o + s) + Q_MS / 2, s })).filter((d) => d.s >= q0), [F, p, o, q0]);
  const lastPub = useMemo(() => [...past].reverse().find((d) => d.y !== null) ?? null, [past]);

  // price axis: computed from what is visible, then glides to it (no jumping while scrolling)
  const yTarget = useMemo<[number, number]>(() => {
    const vis = (tt: number) => tt >= d0 - Q_MS && tt <= d1 + Q_MS;
    const core: number[] = [];
    fut.forEach(({ t: tt, s }) => { if (vis(tt)) core.push(F.p10[s], F.p90[s]); });
    past.forEach((d) => { if (d.spot !== null && vis(d.t)) core.push(d.spot - 40, d.spot + 40); });
    if (core.length === 0) core.push(0, 100);
    const lo = Math.min(...core), hi = Math.max(...core), sp = Math.max(40, hi - lo);
    const real = past.filter((d) => d.y !== null && vis(d.t)).map((d) => d.y as number);
    const n = scaleLinear().domain([Math.max(Math.min(lo, ...real), lo - 0.6 * sp), Math.min(Math.max(hi, ...real), hi + 0.6 * sp)]).nice(5).domain();
    return [n[0], n[1]];
  }, [F, fut, past, d0, d1]);
  const yDom = useSmoothRange(yTarget, 90);
  const y = useMemo(() => scaleLinear().domain(yDom).range([M.t + PLOT_H, M.t]).clamp(true), [yDom]);

  const dirY = M.t + PLOT_H + DIR_GAP;
  const riskTop = dirY + DIR_H + RISK_GAP;
  const riskMid = riskTop + RISK_HALF;
  const axisY = riskMid + RISK_HALF + 10;
  const Hgt = axisY + AXIS_H;

  const band = area<{ t: number; s: number }>().x((d) => x(d.t)).y0((d) => y(F.p10[d.s])).y1((d) => y(F.p90[d.s])).curve(curveMonotoneX);
  const med = line<{ t: number; s: number }>().x((d) => x(d.t)).y((d) => y(F.p50[d.s])).curve(curveMonotoneX);
  const step = (acc: (d: (typeof past)[number]) => number | null) =>
    line<(typeof past)[number]>().defined((d) => acc(d) !== null).x((d) => x(d.t)).y((d) => y(acc(d) as number)).curve(curveStepAfter);
  const realLine = step((d) => d.y)([...past.filter((d) => d.y !== null), ...(lastPub ? [{ ...lastPub, t: lastPub.t + Q_MS }] : [])]);
  const spotLine = step((d) => d.spot)(past);
  const zoneHi = area<(typeof past)[number]>().defined((d) => d.spot !== null).x((d) => x(d.t)).y0(M.t).y1((d) => y((d.spot as number) + 50)).curve(curveStepAfter);
  const zoneLo = area<(typeof past)[number]>().defined((d) => d.spot !== null).x((d) => x(d.t)).y0(M.t + PLOT_H).y1((d) => y((d.spot as number) - 50)).curve(curveStepAfter);

  const tstep = tickStep(d1 - d0);
  const minor = Math.max(Q_MS, tstep / 2);
  const ticks: { t: number; major: boolean; midnight: boolean }[] = [];
  for (let h = Math.ceil(d0 / minor) * minor; h <= d1; h += minor) {
    const midnight = hourOf(h) === 0 && new Date(h).getUTCMinutes() === 0;
    ticks.push({ t: h, major: Math.round(h / minor) % Math.round(tstep / minor) === 0 || midnight, midnight });
  }

  const xT = x(T);
  const xH = x(horizonEnd);
  const cell = (gi: number) => [x(qMs(p, gi)), x(qMs(p, gi + 1))] as const;
  const inPlot = (px: number) => px >= M.l && px <= W - M.r;
  const hs = hover !== null && hover >= o + q0 && hover < o + STEPS ? hover - o : null;
  const hp = hover !== null ? past.find((d) => d.gi === hover) : undefined;
  const endS = fut.reduce((acc, d) => (x(d.t) <= W - M.r ? d.s : acc), -1);
  const lastSpot = [...past].reverse().find((d) => d.spot !== null && x(d.t) <= W - M.r)?.spot ?? null;
  const prevLabel = hhmm(madeAt - H_MS, lang);

  // drag pans; a press without movement on a forecast quarter opens its detail
  const drag = useRef<{ x: number; last: number; moved: boolean } | null>(null);
  const toPx = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect();
    return ((e.clientX - r.left) / r.width) * W;
  };
  function onPointerDown(e: React.PointerEvent<SVGSVGElement>) {
    if (e.button !== 0) return;
    const px = toPx(e);
    drag.current = { x: px, last: px, moved: false };
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent<SVGSVGElement>) {
    const px = toPx(e);
    if (drag.current) {
      if (Math.abs(px - drag.current.x) > 4) { drag.current.moved = true; setDragging(true); }
      if (drag.current.moved) { onPan(-(px - drag.current.last) * msPerPx); drag.current.last = px; setHover(null); return; }
    }
    if (!inPlot(px)) return setHover(null);
    setHover(Math.floor((x.invert(px) - p.t0) / Q_MS));
  }
  function onPointerUp(e: React.PointerEvent<SVGSVGElement>) {
    const d = drag.current;
    drag.current = null;
    setDragging(false);
    if (!d || d.moved) return;
    const gi = Math.floor((x.invert(toPx(e)) - p.t0) / Q_MS);
    if (gi >= o + q0 && gi < o + STEPS) onQuarter(gi - o);
  }

  const cursor = dragging ? "cursor-grabbing" : hs !== null ? "cursor-pointer" : "cursor-grab";
  const btn = "inline-flex h-8 w-8 items-center justify-center rounded-md border border-rule bg-sheet text-ink-2 transition-[color,transform,border-color] duration-150 ease-out hover:border-bank/40 hover:text-bank active:scale-[0.96]";

  return (
    <div ref={wrap} className="relative w-full select-none">
      <div className="mb-1.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-ink-3">
          <span className="inline-flex items-center gap-1.5"><MousePointerClick size={14} strokeWidth={1.75} className="text-bank" />{t(lang, "tcHintClick")}</span>
          <span className="inline-flex items-center gap-1.5"><Move size={14} strokeWidth={1.75} className="text-bank" />{t(lang, "tcHintMove")}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="num mr-1 text-[12.5px] text-ink-3">{t(lang, "tcSpan", { h: Math.round(span / H_MS) })}</span>
          <button type="button" className={btn} onClick={() => onZoom(0.5)} aria-label={t(lang, "zoomIn")} title={t(lang, "zoomIn")}><ZoomIn size={16} strokeWidth={1.75} /></button>
          <button type="button" className={btn} onClick={() => onZoom(2)} aria-label={t(lang, "zoomOut")} title={t(lang, "zoomOut")}><ZoomOut size={16} strokeWidth={1.75} /></button>
          <button type="button" className={btn} onClick={onResetZoom} aria-label={t(lang, "zoomReset")} title={t(lang, "zoomReset")}><Maximize2 size={15} strokeWidth={1.75} /></button>
        </div>
      </div>

      <svg ref={svgRef} width={W} height={Hgt} viewBox={`0 0 ${W} ${Hgt}`} role="img"
        aria-label={`${t(lang, "chartTitle")}. ${t(lang, "sMedian")} ${fmt0(F.p50[0])}–${fmt0(F.p50[STEPS - 1])} €/MWh.`}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
        onPointerLeave={() => { if (!drag.current) setHover(null); }}
        className={`block touch-none ${cursor}`}>
        <defs>
          <clipPath id={`c-${uid}`}><rect x={M.l} y={0} width={W - M.l - M.r} height={Hgt} /></clipPath>
          {/* the forecast side brightens gradually from now: one surface, no hard edge */}
          <linearGradient id={`f-${uid}`} gradientUnits="userSpaceOnUse" x1={xT} x2={xT + 90} y1="0" y2="0">
            <stop offset="0" stopColor="hsl(var(--sheet))" stopOpacity="0" />
            <stop offset="1" stopColor="hsl(var(--sheet))" stopOpacity="1" />
          </linearGradient>
          <linearGradient id={`b-${uid}`} gradientUnits="userSpaceOnUse" x1={xT} x2={xT + 70} y1="0" y2="0">
            <stop offset="0" stopColor="hsl(var(--fan-inner))" stopOpacity="0.15" />
            <stop offset="1" stopColor="hsl(var(--fan-inner))" stopOpacity="0.6" />
          </linearGradient>
          <pattern id={`h-${uid}`} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="7" stroke="hsl(var(--rule))" strokeWidth="1.6" />
          </pattern>
        </defs>

        <g clipPath={`url(#c-${uid})`}>
          {/* surfaces */}
          <rect x={xT} y={M.t} width={Math.max(0, xH - xT)} height={axisY - M.t} fill={`url(#f-${uid})`} />
          {xH < W - M.r && <rect x={xH} y={M.t} width={W - M.r - xH} height={PLOT_H} fill={`url(#h-${uid})`} opacity={0.55} />}
          {focus && (() => { const a = cell(o + focus.a)[0], b = cell(o + focus.b)[1]; return <rect x={a} y={M.t} width={b - a} height={axisY - M.t} fill="hsl(var(--accent))" />; })()}
          {hs !== null && (() => { const [a, b] = cell(o + hs); return <rect x={a} y={M.t} width={b - a} height={axisY - M.t} fill="hsl(var(--bank))" fillOpacity={0.07} />; })()}

          {/* gridlines and midnights */}
          {y.ticks(5).map((v) => <line key={v} x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} stroke="hsl(var(--rule))" strokeWidth={v === 0 ? 1.1 : 0.6} />)}
          {ticks.filter((k) => k.midnight).map((k) => <line key={k.t} x1={x(k.t)} x2={x(k.t)} y1={M.t} y2={axisY} stroke="hsl(var(--ink-3))" strokeOpacity={0.3} strokeDasharray="2 3" />)}

          {zones && <path d={zoneHi(past) ?? ""} fill="hsl(var(--verm))" fillOpacity={0.07} />}
          {zones && <path d={zoneLo(past) ?? ""} fill="hsl(var(--teal))" fillOpacity={0.08} />}

          {/* price */}
          <path d={spotLine ?? ""} fill="none" stroke="hsl(var(--ink-2))" strokeWidth={1.5} strokeDasharray="1.5 3.5" strokeLinecap="round" />
          <path d={band(fut) ?? ""} fill={`url(#b-${uid})`} />
          <path d={med(fut) ?? ""} fill="none" stroke="hsl(var(--bank))" strokeWidth={2.4} strokeDasharray="7 4" strokeLinecap="round" />
          <path d={realLine ?? ""} fill="none" stroke="hsl(var(--ink))" strokeWidth={2} strokeLinejoin="round" />
          {/* bridge from the last published price to the forecast's first quarter: one continuous story */}
          {lastPub && lastPub.y !== null && (
            <>
              <line x1={x(lastPub.t + Q_MS)} y1={y(lastPub.y)} x2={x(fut[0].t)} y2={y(F.p50[fut[0].s])} stroke="hsl(var(--ink-3))" strokeWidth={1.3} strokeDasharray="2 3" />
              <circle cx={x(lastPub.t + Q_MS)} cy={y(lastPub.y)} r={3.6} fill="hsl(var(--sheet))" stroke="hsl(var(--ink))" strokeWidth={2} />
            </>
          )}

          {/* balancing direction: share of up / none / down per quarter (left: what happened) */}
          {past.map((d) => {
            if (d.dir === null) return null;
            const [a, b] = cell(d.gi);
            return <rect key={`pd${d.gi}`} x={a} y={dirY} width={Math.max(1, b - a - 0.8)} height={DIR_H}
              fill={d.dir > 0 ? "hsl(var(--verm))" : d.dir < 0 ? "hsl(var(--teal))" : "hsl(var(--rule))"} fillOpacity={0.35} />;
          })}
          {F.pu.map((pu, s) => {
            if (s < q0) return null;
            const [a, b] = cell(o + s);
            const w = Math.max(1, b - a - 0.8);
            const dim = focus && (s < focus.a || s > focus.b) ? 0.4 : 1;
            return (
              <g key={`fd${o + s}`} opacity={dim}>
                <rect x={a} y={dirY} width={w} height={DIR_H} fill="hsl(var(--rule))" />
                <rect x={a} y={dirY} width={w} height={DIR_H} fill="hsl(var(--verm))" fillOpacity={0.85} style={grow("top", pu)} />
                <rect x={a} y={dirY} width={w} height={DIR_H} fill="hsl(var(--teal))" fillOpacity={0.85} style={grow("bottom", F.pd[s])} />
              </g>
            );
          })}

          {/* spike risk: high above the line, low below; dashed = alert threshold; tick = an hour earlier */}
          <line x1={M.l} x2={W - M.r} y1={riskMid} y2={riskMid} stroke="hsl(var(--ink-3))" strokeWidth={0.8} />
          <line x1={xT} x2={W - M.r} y1={riskMid - HI_THR * RISK_HALF} y2={riskMid - HI_THR * RISK_HALF} stroke="hsl(var(--verm))" strokeOpacity={0.5} strokeDasharray="3 3" />
          <line x1={xT} x2={W - M.r} y1={riskMid + LO_THR * RISK_HALF} y2={riskMid + LO_THR * RISK_HALF} stroke="hsl(var(--teal))" strokeOpacity={0.5} strokeDasharray="3 3" />
          {past.map((d) => {
            if (d.y === null || d.spot === null) return null;
            const hiS = d.y > d.spot + 50, loS = d.y < d.spot - 50;
            if (!hiS && !loS) return null;
            const [a, b] = cell(d.gi);
            return <rect key={`ps${d.gi}`} x={a} y={hiS ? riskTop : riskMid} width={Math.max(1, b - a - 0.8)} height={RISK_HALF}
              fill={hiS ? "hsl(var(--verm))" : "hsl(var(--teal))"} fillOpacity={0.35} />;
          })}
          {F.hi.map((hi, s) => {
            if (s < q0) return null;
            const lo = F.lo[s];
            const [a, b] = cell(o + s);
            const w = Math.max(1, b - a - 0.8);
            const dim = focus && (s < focus.a || s > focus.b) ? 0.4 : 1;
            const ph = prevAt("hi", s), pl = prevAt("lo", s);
            return (
              <g key={`fr${o + s}`} opacity={dim}>
                <rect x={a} y={riskTop} width={w} height={RISK_HALF} fill="hsl(var(--verm))" fillOpacity={hi >= HI_THR ? 1 : 0.5} style={grow("bottom", hi)} />
                <rect x={a} y={riskMid} width={w} height={RISK_HALF} fill="hsl(var(--teal))" fillOpacity={lo >= LO_THR ? 1 : 0.5} style={grow("top", lo)} />
                {ph !== null && Math.abs(ph - hi) >= 0.05 && <line x1={a} x2={a + w} y1={riskMid - ph * RISK_HALF} y2={riskMid - ph * RISK_HALF} stroke="hsl(var(--ink))" strokeOpacity={0.6} strokeWidth={1.4} />}
                {pl !== null && Math.abs(pl - lo) >= 0.05 && <line x1={a} x2={a + w} y1={riskMid + pl * RISK_HALF} y2={riskMid + pl * RISK_HALF} stroke="hsl(var(--ink))" strokeOpacity={0.6} strokeWidth={1.4} />}
              </g>
            );
          })}

          {/* now */}
          <line x1={xT} x2={xT} y1={M.t - 18} y2={axisY} stroke="hsl(var(--bank))" strokeWidth={1.6} />
          {xT - M.l > 110 && <text x={xT - 12} y={M.t + 16} textAnchor="end" className="fill-ink-3 text-[11.5px] font-semibold uppercase tracking-[0.08em]">← {t(lang, "tcKnown")}</text>}
          {W - M.r - xT > 110 && <text x={xT + 12} y={M.t + 16} className="fill-bank text-[11.5px] font-semibold uppercase tracking-[0.08em]">{t(lang, "tcForecast")} →</text>}
          {xH < W - M.r - 100 && <text x={xH + 10} y={M.t + 16} className="fill-ink-3 text-[11.5px]">{t(lang, "tcBeyond")}</text>}
          {hover !== null && <line x1={x(qMs(p, hover) + Q_MS / 2)} x2={x(qMs(p, hover) + Q_MS / 2)} y1={M.t} y2={axisY} stroke="hsl(var(--ink))" strokeOpacity={0.25} />}
        </g>

        {/* now pill (outside the clip so it is never cut) */}
        {xT >= M.l && xT <= W - M.r && (
          <g>
            <rect x={xT - 38} y={M.t - 36} width={76} height={22} rx={11} fill="hsl(var(--bank))" />
            <text x={xT} y={M.t - 21} textAnchor="middle" className="num fill-white text-[12px] font-semibold">{t(lang, "tcNow")} {hhmm(T, lang)}</text>
          </g>
        )}

        {/* left: axis and row labels */}
        <text x={M.l - 10} y={M.t - 14} textAnchor="end" className="fill-ink-3 text-[12px]">€/MWh</text>
        {y.ticks(5).map((v) => <text key={v} x={M.l - 10} y={y(v)} dy="0.32em" textAnchor="end" className="num fill-ink-3 text-[12px]">{fmt0(v)}</text>)}
        <text x={6} y={dirY - 7} className="fill-ink text-[13px] font-semibold">{t(lang, "direction")}</text>
        <g className="text-[11px]">
          <rect x={6} y={dirY + 4} width={8} height={8} rx={1.5} fill="hsl(var(--verm))" /><text x={18} y={dirY + 11} className="fill-ink-2">{t(lang, "up")}</text>
          <rect x={46} y={dirY + 4} width={8} height={8} rx={1.5} fill="hsl(var(--rule))" /><text x={58} y={dirY + 11} className="fill-ink-2">{t(lang, "none")}</text>
          <rect x={6} y={dirY + 16} width={8} height={8} rx={1.5} fill="hsl(var(--teal))" /><text x={18} y={dirY + 23} className="fill-ink-2">{t(lang, "down")}</text>
        </g>
        <text x={6} y={riskTop - 7} className="fill-ink text-[13px] font-semibold">{t(lang, "tcRisk")}</text>
        <text x={6} y={riskTop + RISK_HALF / 2} dy="0.32em" className="fill-verm text-[12px] font-semibold">{t(lang, "tcHigh")}</text>
        <text x={6} y={riskMid + RISK_HALF / 2} dy="0.32em" className="fill-teal text-[12px] font-semibold">{t(lang, "tcLow")}</text>
        <text x={W - M.r + 8} y={riskMid - HI_THR * RISK_HALF} dy="0.32em" className="num fill-verm text-[11px]">40 %</text>
        <text x={W - M.r + 8} y={riskMid + LO_THR * RISK_HALF} dy="0.32em" className="num fill-teal text-[11px]">50 %</text>
        {prev && <text x={W - M.r + 8} y={riskMid} dy="0.32em" className="fill-ink-3 text-[10.5px]">▔ {prevLabel}</text>}

        {/* right: direct labels */}
        {endS >= 0 && (
          <g className="text-[12.5px] font-semibold">
            <text x={Math.min(W - M.r + 8, x(qMs(p, o + endS) + Q_MS / 2) + 8)} y={y(F.p50[endS])} dy="0.32em" className="fill-bank">{t(lang, "tcExpected")}</text>
            <text x={Math.min(W - M.r + 8, x(qMs(p, o + endS) + Q_MS / 2) + 8)} y={y(F.p90[endS])} dy="0.32em" className="fill-ink-3 font-normal">{t(lang, "tcRangeTop")}</text>
          </g>
        )}
        {lastSpot !== null && <text x={W - M.r + 8} y={y(lastSpot)} dy="0.32em" className="fill-ink-2 text-[12.5px]">{t(lang, "tcDayAhead")}</text>}

        {/* time axis */}
        <line x1={M.l} x2={W - M.r} y1={axisY} y2={axisY} stroke="hsl(var(--ink-3))" strokeWidth={0.75} />
        {ticks.map(({ t: h, major, midnight }) => (
          <g key={h}>
            <line x1={x(h)} x2={x(h)} y1={axisY} y2={axisY + (major ? 6 : 3)} stroke="hsl(var(--ink-3))" />
            {major && !midnight && <text x={x(h)} y={axisY + 19} textAnchor="middle" className="num fill-ink-3 text-[12px]">{hhmm(h, lang)}</text>}
            {midnight && <text x={x(h)} y={axisY + 19} textAnchor="middle" className="fill-ink text-[12.5px] font-bold">{dateShort(h, lang)}</text>}
          </g>
        ))}
      </svg>

      {hover !== null && !dragging && (hs !== null || hp) && (() => {
        // compact card in the margin above the plot, centred on the hovered quarter, with a pointer down to it
        const cw = hs !== null ? 540 : 400;
        const xc = x(qMs(p, hover) + Q_MS / 2);
        const left = Math.max(0, Math.min(W - cw, xc - cw / 2));
        const top = (svgRef.current && wrap.current ? svgRef.current.getBoundingClientRect().top - wrap.current.getBoundingClientRect().top : 40) + 4;
        return (
          <div className="pointer-events-none absolute z-10 rounded-lg border border-rule bg-sheet px-3 py-1.5 text-[12.5px] shadow-[0_6px_18px_-10px_rgba(20,34,51,0.45)]"
            style={{ left, top, width: cw }}>
            <span className="absolute -bottom-[5px] h-2.5 w-2.5 rotate-45 border-b border-r border-rule bg-sheet" style={{ left: Math.max(8, Math.min(cw - 18, xc - left - 5)) }} />
            <div className="num flex items-center gap-x-3 whitespace-nowrap text-ink-2">
              <span className="font-semibold text-ink">{hhmm(qMs(p, hover), lang)}–{hhmm(qMs(p, hover + 1), lang)}</span>
              <span className={`rounded-full px-1.5 py-px text-[10.5px] font-semibold ${hs !== null ? "bg-bank/10 text-bank" : "bg-paper text-ink-3"}`}>{t(lang, hs !== null ? "tcForecast" : "tcKnown")}</span>
              {hs === null && hp && (
                <>
                  <span>{t(lang, "realised")} <b className="text-ink">{hp.y === null ? (hover < o ? t(lang, "tcNotYet") : "–") : `${fmt0(hp.y)} €/MWh`}</b></span>
                  <span>{t(lang, "tcDayAhead")} {hp.spot === null ? "–" : `${fmt0(hp.spot)} €/MWh`}</span>
                </>
              )}
              {hs !== null && (
                <>
                  <span>{t(lang, "tcExpected")} <b className="text-ink">{fmt0(F.p50[hs])} €/MWh</b></span>
                  <span>{t(lang, "tcRange")} {fmt0(F.p10[hs])}–{fmt0(F.p90[hs])}</span>
                  {hp?.spot !== null && hp?.spot !== undefined && <span>{t(lang, "tcDayAhead")} {fmt0(hp.spot)}</span>}
                </>
              )}
            </div>
            <div className="num mt-0.5 flex items-center gap-x-3 whitespace-nowrap text-ink-2">
              {hs === null && hp && <span>{t(lang, "direction")}: {hp.dir === null ? "–" : t(lang, hp.dir > 0 ? "up" : hp.dir < 0 ? "down" : "none")}</span>}
              {hs !== null && (
                <>
                  <span className="inline-flex h-1.5 w-14 overflow-hidden rounded-full">
                    <span className="bg-verm" style={{ width: `${F.pu[hs] * 100}%` }} /><span className="bg-rule" style={{ width: `${F.pn[hs] * 100}%` }} /><span className="bg-teal" style={{ width: `${F.pd[hs] * 100}%` }} />
                  </span>
                  <span><span className="text-verm">{t(lang, "up")} {pct(F.pu[hs])}</span> · <span className="text-teal">{t(lang, "down")} {pct(F.pd[hs])}</span></span>
                  <span className="text-verm">{t(lang, "tcHiShort")} {pct(F.hi[hs])}<Delta v={F.hi[hs]} prev={prevAt("hi", hs)} /></span>
                  <span className="text-teal">{t(lang, "tcLoShort")} {pct(F.lo[hs])}<Delta v={F.lo[hs]} prev={prevAt("lo", hs)} /></span>
                  <span className="ml-auto inline-flex items-center gap-1 font-semibold text-bank"><MousePointerClick size={12} strokeWidth={2} />{t(lang, "tcClick")}</span>
                </>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

export function Row({ k, v, strong }: { k: string; v: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-4 ${strong ? "font-semibold text-ink" : "text-ink-2"}`}>
      <span>{k}</span><span className="num">{v}</span>
    </div>
  );
}

function Delta({ v, prev }: { v: number; prev: number | null }) {
  const d = prev === null ? 0 : Math.round((v - prev) * 100);
  return d === 0 ? null : <span className="ml-1 text-[11px] text-ink-3">{d > 0 ? "▲" : "▼"}{Math.abs(d)}</span>;
}

export function Risk({ label, v, prev, cls, since, lang }: { label: string; v: number; prev: number | null; cls: string; since: string; lang: Lang }) {
  const d = prev === null ? null : Math.round((v - prev) * 100);
  return (
    <div className={`num mt-0.5 flex justify-between gap-4 ${cls}`}>
      <span>{label}</span>
      <span>{pct(v)}{d !== null && d !== 0 && <span className="ml-1.5 text-[11.5px] text-ink-3">{d > 0 ? "▲" : "▼"} {Math.abs(d)} {t(lang, "tcPts", { t: since })}</span>}</span>
    </div>
  );
}

/** legend in words for the chart's few marks */
export function TimeLegend({ lang }: { lang: Lang }) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px] text-ink-2">
      <span className="inline-flex items-center gap-2"><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="hsl(var(--ink))" strokeWidth="2" /></svg>{t(lang, "realised")}</span>
      <span className="inline-flex items-center gap-2"><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="hsl(var(--bank))" strokeWidth="2.4" strokeDasharray="7 4" /></svg>{t(lang, "sMedian")}</span>
      <span className="inline-flex items-center gap-2"><svg width="22" height="10"><rect width="22" height="10" rx="2" fill="hsl(var(--fan-inner))" fillOpacity="0.6" /></svg>{t(lang, "sBand")}</span>
      <span className="inline-flex items-center gap-2"><svg width="22" height="8"><line x1="1" x2="21" y1="4" y2="4" stroke="hsl(var(--ink-2))" strokeWidth="1.5" strokeDasharray="1.5 3.5" strokeLinecap="round" /></svg>{t(lang, "sSpot")}</span>
    </div>
  );
}

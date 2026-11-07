import { useEffect, useId, useMemo, useRef, useState } from "react";
import { scaleLinear } from "d3-scale";
import { area, curveMonotoneX, curveStepAfter, line } from "d3-shape";
import { Maximize2, ZoomIn, ZoomOut } from "lucide-react";
import type { Alert, Period } from "@/data/types";
import { STEPS, forecastAt, known, qMs, reviewMin, reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { Q_MS, dateShort, hhmm, hourOf, type Lang } from "@/lib/time";
import { tickStep } from "@/lib/useZoom";

const H_MS = 3600_000;
export const BACK = 0.375; // share of the window left of "now"
const M = { l: 118, r: 92, t: 34 };
const PLOT_H = 280, RISK_GAP = 16, RISK_H = 14, BAL_GAP = 18, BAL_HALF = 46, AXIS_H = 36;

const fmt0 = (v: number) => Math.round(v).toLocaleString("en-US").replace(/,/g, " ");
const pct = (v: number) => `${Math.round(v * 100)} %`;

/**
 * Price, price risk and balancing need on ONE time axis. Scrolling, dragging or the slider move through time:
 * the review moment ("now") travels with the view, so nothing published after it is ever shown.
 * Left of "now": what was known (realised price, realised direction). Right: the forecast made at "now".
 */
export function TimeChart({ p, i, win, lang, focus, zones, onPan, onPanEnd, onZoom, onResetZoom, span, onQuarter }: {
  p: Period; i: number; win: [number, number]; lang: Lang; focus: Alert | null; zones: boolean;
  onPan: (ms: number) => void; onPanEnd: () => void; onZoom: (factor: number) => void; onResetZoom: () => void;
  span: number; onQuarter: (s: number) => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [W, setW] = useState(1000);
  const [hover, setHover] = useState<number | null>(null);
  const uid = useId().replace(/:/g, "");

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(640, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const [d0, d1] = win;
  const x = useMemo(() => scaleLinear().domain([d0, d1]).range([M.l, W - M.r]), [d0, d1, W]);
  const msPerPx = (d1 - d0) / (W - M.l - M.r);

  // wheel: scroll pans through time (either wheel direction); ctrl/cmd + wheel or a pinch zooms
  const panRef = useRef({ onPan, onPanEnd, onZoom, msPerPx });
  panRef.current = { onPan, onPanEnd, onZoom, msPerPx };
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    let idle: number | undefined;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const c = panRef.current;
      if (e.ctrlKey || e.metaKey) { c.onZoom(Math.exp(e.deltaY * 0.01)); return; }
      const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      c.onPan(d * c.msPerPx);
      window.clearTimeout(idle);
      idle = window.setTimeout(() => panRef.current.onPanEnd(), 180);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => { el.removeEventListener("wheel", onWheel); window.clearTimeout(idle); };
  }, []);

  // drag pans; a press without movement is a click (opens the quarter under the pointer)
  const drag = useRef<{ x: number; last: number; moved: boolean } | null>(null);
  const toPx = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect();
    return ((e.clientX - r.left) / r.width) * W;
  };

  const T = reviewMs(p, i);
  const Tmin = reviewMin(p, i);
  const o = p.origins[i];
  const F = useMemo(() => forecastAt(p, i), [p, i]);
  const horizonEnd = qMs(p, o + STEPS);

  // the visible quarter-hours (grid indices), known values only
  const g0 = Math.max(0, Math.floor((d0 - p.t0) / Q_MS) - 1);
  const g1 = Math.min(p.nq - 1, Math.ceil((d1 - p.t0) / Q_MS) + 1);
  const past = useMemo(() => {
    const out: { gi: number; t: number; y: number | null; spot: number | null; dir: number | null }[] = [];
    for (let gi = g0; gi <= g1; gi++) {
      out.push({
        gi, t: qMs(p, gi),
        y: gi < o ? known(p.imb, p.imb_fu, gi, Tmin) : null,
        spot: known(p.spot, p.spot_fu, gi, Tmin),
        dir: gi < o ? known(p.dir, p.dir_fu, gi, Tmin) : null,
      });
    }
    return out;
  }, [p, g0, g1, o, Tmin]);
  const fut = useMemo(() => F.p50.map((_, s) => ({ t: qMs(p, o + s) + Q_MS / 2, s })), [F, p, o]);
  const lastPub = useMemo(() => [...past].reverse().find((d) => d.y !== null) ?? null, [past]);

  const y = useMemo(() => {
    const vis = (tt: number) => tt >= d0 - Q_MS && tt <= d1 + Q_MS;
    const core: number[] = [];
    fut.forEach(({ t: tt, s }) => { if (vis(tt)) core.push(F.p10[s], F.p90[s]); });
    past.forEach((d) => { if (d.spot !== null && vis(d.t)) core.push(d.spot - 40, d.spot + 40); });
    if (core.length === 0) core.push(0, 100);
    const lo = Math.min(...core), hi = Math.max(...core), sp = Math.max(40, hi - lo);
    const real = past.filter((d) => d.y !== null && vis(d.t)).map((d) => d.y as number);
    const yMin = Math.max(Math.min(lo, ...real), lo - 0.6 * sp);
    const yMax = Math.min(Math.max(hi, ...real), hi + 0.6 * sp);
    return scaleLinear().domain([yMin, yMax]).range([M.t + PLOT_H, M.t]).nice(5).clamp(true);
  }, [F, fut, past, d0, d1]);

  const riskY = M.t + PLOT_H + RISK_GAP;
  const balY = riskY + RISK_H + BAL_GAP;      // top of the "grid short" half
  const balMid = balY + BAL_HALF;
  const axisY = balMid + BAL_HALF + 8;
  const Hgt = axisY + AXIS_H;

  const band = area<{ t: number; s: number }>().x((d) => x(d.t)).y0((d) => y(F.p10[d.s])).y1((d) => y(F.p90[d.s])).curve(curveMonotoneX);
  const med = line<{ t: number; s: number }>().x((d) => x(d.t)).y((d) => y(F.p50[d.s])).curve(curveMonotoneX);
  const step = (acc: (d: (typeof past)[number]) => number | null) =>
    line<(typeof past)[number]>().defined((d) => acc(d) !== null).x((d) => x(d.t)).y((d) => y(acc(d) as number)).curve(curveStepAfter);
  const realLine = step((d) => d.y)([...past.filter((d) => d.y !== null), ...(lastPub ? [{ ...lastPub, t: lastPub.t + Q_MS }] : [])]);
  const spotLine = step((d) => d.spot)(past);
  const zoneHi = area<(typeof past)[number]>().defined((d) => d.spot !== null).x((d) => x(d.t)).y0(M.t).y1((d) => y((d.spot as number) + 50)).curve(curveStepAfter);
  const zoneLo = area<(typeof past)[number]>().defined((d) => d.spot !== null).x((d) => x(d.t)).y0(M.t + PLOT_H).y1((d) => y((d.spot as number) - 50)).curve(curveStepAfter);

  // ticks: hours (labels every tickStep), local midnights get the date
  const tstep = tickStep(d1 - d0);
  const minor = Math.max(Q_MS, tstep / 2);
  const ticks: { t: number; major: boolean; midnight: boolean }[] = [];
  for (let h = Math.ceil(d0 / minor) * minor; h <= d1; h += minor) {
    const midnight = hourOf(h) === 0 && new Date(h).getUTCMinutes() === 0;
    ticks.push({ t: h, major: Math.round(h / minor) % Math.round(tstep / minor) === 0 || midnight, midnight });
  }

  const xT = x(T);
  const cell = (gi: number) => [x(qMs(p, gi)), x(qMs(p, gi + 1))] as const;
  const inPlot = (px: number) => px >= M.l && px <= W - M.r;
  const hs = hover !== null && hover >= o && hover < o + STEPS ? hover - o : null;
  const hp = hover !== null ? past.find((d) => d.gi === hover) : undefined;

  // direct labels at the end of the visible forecast (a legend you do not have to decode)
  const endS = fut.reduce((acc, d) => (x(d.t) <= W - M.r ? d.s : acc), -1);
  const lastSpot = [...past].reverse().find((d) => d.spot !== null && x(d.t) <= W - M.r)?.spot ?? null;

  function onPointerDown(e: React.PointerEvent<SVGSVGElement>) {
    if (e.button !== 0) return;
    const px = toPx(e);
    drag.current = { x: px, last: px, moved: false };
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent<SVGSVGElement>) {
    const px = toPx(e);
    if (drag.current) {
      if (Math.abs(px - drag.current.x) > 4) drag.current.moved = true;
      if (drag.current.moved) {
        onPan(-(px - drag.current.last) * msPerPx);
        drag.current.last = px;
        setHover(null);
        return;
      }
    }
    if (!inPlot(px)) return setHover(null);
    setHover(Math.floor((x.invert(px) - p.t0) / Q_MS));
  }
  function onPointerUp(e: React.PointerEvent<SVGSVGElement>) {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (d.moved) { onPanEnd(); return; }
    const gi = Math.floor((x.invert(toPx(e)) - p.t0) / Q_MS);
    if (gi >= o && gi < o + STEPS) onQuarter(gi - o);
  }

  const btn = "inline-flex h-8 w-8 items-center justify-center rounded-md border border-rule bg-sheet text-ink-2 transition-[color,transform] duration-150 ease-out hover:text-bank active:scale-[0.96] disabled:opacity-40";
  const spanH = Math.round(span / H_MS);

  return (
    <div ref={wrap} className="relative w-full select-none">
      <div className="absolute right-0 top-0 z-[2] flex items-center gap-1.5">
        <span className="num mr-1 text-[12.5px] text-ink-3">{t(lang, "tcSpan", { h: spanH })}</span>
        <button type="button" className={btn} onClick={() => onZoom(0.5)} aria-label={t(lang, "zoomIn")} title={t(lang, "zoomIn")}><ZoomIn size={16} strokeWidth={1.75} /></button>
        <button type="button" className={btn} onClick={() => onZoom(2)} aria-label={t(lang, "zoomOut")} title={t(lang, "zoomOut")}><ZoomOut size={16} strokeWidth={1.75} /></button>
        <button type="button" className={btn} onClick={onResetZoom} aria-label={t(lang, "zoomReset")} title={t(lang, "zoomReset")}><Maximize2 size={15} strokeWidth={1.75} /></button>
      </div>

      <svg ref={svgRef} width={W} height={Hgt} viewBox={`0 0 ${W} ${Hgt}`} role="img"
        aria-label={`${t(lang, "chartTitle")}. ${t(lang, "sMedian")} ${fmt0(F.p50[0])}–${fmt0(F.p50[STEPS - 1])} €/MWh.`}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerLeave={() => setHover(null)}
        className="block touch-none cursor-grab active:cursor-grabbing">
        <defs>
          <clipPath id={`c-${uid}`}><rect x={M.l} y={0} width={W - M.l - M.r} height={Hgt} /></clipPath>
          <pattern id={`h-${uid}`} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="8" stroke="hsl(var(--rule))" strokeWidth="2" />
          </pattern>
        </defs>

        <g clipPath={`url(#c-${uid})`}>
          {/* forecast part on the lighter sheet; beyond the 10-hour horizon hatched */}
          <rect x={xT} y={M.t} width={Math.max(0, x(horizonEnd) - xT)} height={axisY - M.t} fill="hsl(var(--sheet))" />
          {x(horizonEnd) < W - M.r && <rect x={x(horizonEnd)} y={M.t} width={W - M.r - x(horizonEnd)} height={PLOT_H} fill={`url(#h-${uid})`} opacity={0.6} />}
          {focus && (() => { const a = cell(o + focus.a)[0], b = cell(o + focus.b)[1]; return <rect x={a} y={M.t} width={b - a} height={axisY - M.t} fill="hsl(var(--accent))" />; })()}

          {/* gridlines and midnights */}
          {y.ticks(5).map((v) => <line key={v} x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} stroke="hsl(var(--rule))" strokeWidth={v === 0 ? 1.2 : 0.7} />)}
          {ticks.filter((k) => k.midnight).map((k) => <line key={k.t} x1={x(k.t)} x2={x(k.t)} y1={M.t} y2={axisY} stroke="hsl(var(--ink-3))" strokeOpacity={0.35} strokeDasharray="2 3" />)}

          {/* optional spike zones: above spot +50 and below spot −50 */}
          {zones && <path d={zoneHi(past) ?? ""} fill="hsl(var(--verm))" fillOpacity={0.07} />}
          {zones && <path d={zoneLo(past) ?? ""} fill="hsl(var(--teal))" fillOpacity={0.08} />}

          <path d={spotLine ?? ""} fill="none" stroke="hsl(var(--ink-2))" strokeWidth={1.5} strokeDasharray="1.5 3.5" strokeLinecap="round" />
          <path d={band(fut) ?? ""} fill="hsl(var(--fan-inner))" fillOpacity={0.55} />
          <path d={med(fut) ?? ""} fill="none" stroke="hsl(var(--bank))" strokeWidth={2.4} strokeDasharray="7 4" />
          <path d={realLine ?? ""} fill="none" stroke="hsl(var(--ink))" strokeWidth={2} strokeLinejoin="round" />
          {lastPub && lastPub.y !== null && <circle cx={x(lastPub.t + Q_MS)} cy={y(lastPub.y)} r={3.4} fill="hsl(var(--ink))" />}

          {/* price risk strip: realised spikes on the left, forecast risk on the right */}
          {past.map((d) => {
            if (d.y === null || d.spot === null) return null;
            const hiS = d.y > d.spot + 50, loS = d.y < d.spot - 50;
            if (!hiS && !loS) return null;
            const [a, b] = cell(d.gi);
            return <rect key={`r${d.gi}`} x={a} y={riskY} width={Math.max(1, b - a - 1)} height={RISK_H} rx={2} fill={hiS ? "hsl(var(--verm))" : "hsl(var(--teal))"} fillOpacity={0.45} />;
          })}
          {F.hi.map((hi, s) => {
            const lo = F.lo[s];
            const hiL = hi >= 0.55 ? 2 : hi >= 0.4 ? 1 : 0, loL = lo >= 0.65 ? 2 : lo >= 0.5 ? 1 : 0;
            if (!hiL && !loL) return null;
            const isHi = hiL >= loL, lvl = Math.max(hiL, loL);
            const [a, b] = cell(o + s);
            return <rect key={`f${s}`} x={a} y={riskY} width={Math.max(1, b - a - 1)} height={RISK_H} rx={2}
              fill={isHi ? "hsl(var(--verm))" : "hsl(var(--teal))"} fillOpacity={lvl === 2 ? 1 : 0.5} />;
          })}

          {/* balancing need: up above the line, down below. Left: what happened. Right: forecast probabilities. */}
          {past.map((d) => {
            if (d.dir === null || d.dir === 0) return null;
            const [a, b] = cell(d.gi);
            return <rect key={`d${d.gi}`} x={a} y={d.dir > 0 ? balY + 6 : balMid} width={Math.max(1, b - a - 1)} height={BAL_HALF - 6}
              fill={d.dir > 0 ? "hsl(var(--verm))" : "hsl(var(--teal))"} fillOpacity={0.3} />;
          })}
          {F.pu.map((pu, s) => {
            const [a, b] = cell(o + s);
            const w = Math.max(1, b - a - 1.5);
            const dim = focus && (s < focus.a || s > focus.b) ? 0.45 : 1;
            return (
              <g key={`b${s}`} opacity={dim}>
                <rect x={a} y={balMid - pu * BAL_HALF} width={w} height={pu * BAL_HALF} rx={1.5} fill="hsl(var(--verm))" fillOpacity={0.88} />
                <rect x={a} y={balMid} width={w} height={F.pd[s] * BAL_HALF} rx={1.5} fill="hsl(var(--teal))" fillOpacity={0.88} />
              </g>
            );
          })}
          <line x1={M.l} x2={W - M.r} y1={balMid} y2={balMid} stroke="hsl(var(--ink-3))" strokeWidth={0.8} />

          {/* now */}
          <line x1={xT} x2={xT} y1={M.t - 22} y2={axisY} stroke="hsl(var(--bank))" strokeWidth={1.6} />
          <rect x={xT - 30} y={M.t - 30} width={60} height={20} rx={10} fill="hsl(var(--bank))" />
          <text x={xT} y={M.t - 16} textAnchor="middle" className="num fill-white text-[12.5px] font-semibold">{hhmm(T, lang)}</text>
          {xT - M.l > 120 && <text x={xT - 10} y={M.t + 14} textAnchor="end" className="fill-ink-3 text-[12px] font-semibold uppercase tracking-wide">{t(lang, "tcKnown")}</text>}
          {W - M.r - xT > 120 && <text x={xT + 10} y={M.t + 14} className="fill-bank text-[12px] font-semibold uppercase tracking-wide">{t(lang, "tcForecast")}</text>}
          {x(horizonEnd) < W - M.r - 90 && <text x={x(horizonEnd) + 8} y={M.t + 14} className="fill-ink-3 text-[12px]">{t(lang, "tcBeyond")}</text>}

          {/* hover crosshair through all rows */}
          {hover !== null && <line x1={x(qMs(p, hover) + Q_MS / 2)} x2={x(qMs(p, hover) + Q_MS / 2)} y1={M.t} y2={axisY} stroke="hsl(var(--ink))" strokeOpacity={0.35} />}
        </g>

        {/* left: price axis and row labels */}
        <text x={M.l - 10} y={M.t - 12} textAnchor="end" className="fill-ink-3 text-[12px]">€/MWh</text>
        {y.ticks(5).map((v) => <text key={v} x={M.l - 10} y={y(v)} dy="0.32em" textAnchor="end" className="num fill-ink-3 text-[12px]">{fmt0(v)}</text>)}
        <text x={8} y={riskY + RISK_H / 2} dy="0.32em" className="fill-ink-2 text-[13px] font-semibold">{t(lang, "oRisk")}</text>
        <text x={8} y={balY + BAL_HALF / 2} dy="0.32em" className="fill-verm text-[13px] font-semibold">{t(lang, "tcUp")}</text>
        <text x={8} y={balMid + BAL_HALF / 2} dy="0.32em" className="fill-teal text-[13px] font-semibold">{t(lang, "tcDown")}</text>

        {/* right: direct labels */}
        {endS >= 0 && (
          <g className="text-[12.5px] font-semibold">
            <text x={Math.min(W - M.r + 8, x(fut[endS].t) + 8)} y={y(F.p50[endS])} dy="0.32em" className="fill-bank">{t(lang, "tcExpected")}</text>
            <text x={Math.min(W - M.r + 8, x(fut[endS].t) + 8)} y={y(F.p90[endS])} dy="0.32em" className="fill-ink-3 font-normal">{t(lang, "tcRangeTop")}</text>
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

      {hover !== null && (hs !== null || hp) && (
        <div className="pointer-events-none absolute top-10 z-10 min-w-[210px] rounded-lg border border-rule bg-sheet px-3.5 py-2.5 text-[13px] shadow-[0_8px_24px_-10px_rgba(20,34,51,0.4)]"
          style={{ left: Math.min(W - 230, Math.max(0, x(qMs(p, hover)) + 16)) }}>
          <div className="num mb-1.5 font-semibold text-ink">{hhmm(qMs(p, hover), lang)}–{hhmm(qMs(p, hover + 1), lang)}</div>
          {hs === null && hp && (
            <>
              <Row k={t(lang, "realised")} v={hp.y === null ? (hover < o ? t(lang, "tcNotYet") : "–") : `${fmt0(hp.y)} €/MWh`} strong />
              <Row k={t(lang, "sSpot")} v={hp.spot === null ? "–" : `${fmt0(hp.spot)} €/MWh`} />
              {hp.dir !== null && <Row k={t(lang, "direction")} v={t(lang, hp.dir > 0 ? "up" : hp.dir < 0 ? "down" : "none")} />}
            </>
          )}
          {hs !== null && (
            <>
              <Row k={t(lang, "sMedian")} v={`${fmt0(F.p50[hs])} €/MWh`} strong />
              <Row k={t(lang, "sBand")} v={`${fmt0(F.p10[hs])} – ${fmt0(F.p90[hs])}`} />
              {hp?.spot !== null && hp?.spot !== undefined && <Row k={t(lang, "sSpot")} v={`${fmt0(hp.spot)} €/MWh`} />}
              <div className="mt-1.5 flex justify-between gap-4"><span className="text-verm">{t(lang, "up")} {pct(F.pu[hs])}</span><span className="text-teal">{t(lang, "down")} {pct(F.pd[hs])}</span></div>
              <div className="flex justify-between gap-4 text-ink-2"><span>{t(lang, "highRisk")} {pct(F.hi[hs])}</span><span>{t(lang, "lowRisk")} {pct(F.lo[hs])}</span></div>
              <div className="mt-1.5 text-[12px] text-ink-3">{t(lang, "tcClick")}</div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ k, v, strong }: { k: string; v: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-4 ${strong ? "font-semibold text-ink" : "text-ink-2"}`}>
      <span>{k}</span><span className="num">{v}</span>
    </div>
  );
}

/** legend in words for the chart's few marks */
export function TimeLegend({ lang }: { lang: Lang }) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px] text-ink-2">
      <span className="inline-flex items-center gap-2"><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="hsl(var(--ink))" strokeWidth="2" /></svg>{t(lang, "realised")}</span>
      <span className="inline-flex items-center gap-2"><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="hsl(var(--bank))" strokeWidth="2.4" strokeDasharray="7 4" /></svg>{t(lang, "sMedian")}</span>
      <span className="inline-flex items-center gap-2"><svg width="22" height="10"><rect width="22" height="10" fill="hsl(var(--fan-inner))" fillOpacity="0.55" /></svg>{t(lang, "sBand")}</span>
      <span className="inline-flex items-center gap-2"><svg width="22" height="8"><line x1="1" x2="21" y1="4" y2="4" stroke="hsl(var(--ink-2))" strokeWidth="1.5" strokeDasharray="1.5 3.5" strokeLinecap="round" /></svg>{t(lang, "sSpot")}</span>
    </div>
  );
}

export const H = H_MS;

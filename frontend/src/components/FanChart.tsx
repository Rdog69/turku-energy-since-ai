import { useEffect, useId, useMemo, useRef, useState } from "react";
import { scaleLinear } from "d3-scale";
import { area, curveMonotoneX, curveStepAfter, line } from "d3-shape";
import type { Alert, Period } from "@/data/types";
import { STEPS, forecastAt, known, qMs, reviewMin, reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { Q_MS, dateShort, hhmm, hourOf, type Lang } from "@/lib/time";
import { ZoomControls, tickStep, useBind, useDragPan, useZoom } from "@/lib/useZoom";

const H_MS = 3600_000;
const PAST_H = 6;
const FUT_H = 10;
const M = { l: 52, r: 78, t: 46 };
const PLOT_H = 300;
const RIB_GAP = 30, RIB_H = 24, RISK_GAP = 34, RISK_HALF = 30, AXIS_H = 34;

const fmt0 = (v: number) => Math.round(v).toLocaleString("en-US").replace(/,/g, " ");
const pct = (v: number) => `${Math.round(v * 100)} %`;

export function FanChart({ p, i, lang, focus, periodKey, simple = false }: {
  p: Period; i: number; lang: Lang; focus: Alert | null; periodKey: string; simple?: boolean;
}) {
  const L = labels(lang, simple);
  const wrap = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(960);
  const [hover, setHover] = useState<number | null>(null); // grid index under the pointer
  const reduced = useMemo(() => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches, []);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(560, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const T = reviewMs(p, i);
  const Tmin = reviewMin(p, i);
  const o = p.origins[i];
  const F = useMemo(() => forecastAt(p, i), [p, i]);
  const uid = useId().replace(/:/g, "");
  const svgRef = useRef<SVGSVGElement>(null);
  const z = useZoom([T - PAST_H * H_MS, T + FUT_H * H_MS], 45 * 60_000, { l: M.l, r: M.r, w: W });
  useBind(svgRef, z);
  const dp = useDragPan(svgRef, z, W);
  const [d0, d1] = z.domain;

  const ribY = M.t + PLOT_H + RIB_GAP;
  const riskY = ribY + RIB_H + RISK_GAP; // top of the high-risk half
  const baseY = riskY + RISK_HALF;
  const axisY = simple ? M.t + PLOT_H + 10 : baseY + RISK_HALF + 10;
  const H = axisY + AXIS_H;

  const x = useMemo(() => scaleLinear().domain([d0, d1]).range([M.l, W - M.r]), [d0, d1, W]);
  const xT = x(T);

  // what was known at the review time
  const past = useMemo(() => {
    const pts: { t: number; y: number | null; spot: number | null }[] = [];
    for (let gi = o - PAST_H * 4; gi < o + STEPS; gi++) {
      if (gi < 0 || gi >= p.nq) continue;
      pts.push({ t: qMs(p, gi), y: gi < o ? known(p.imb, p.imb_fu, gi, Tmin) : null, spot: known(p.spot, p.spot_fu, gi, Tmin) });
    }
    return pts;
  }, [p, o, Tmin]);
  const lastPub = useMemo(() => [...past].reverse().find((d) => d.y !== null) ?? null, [past]);
  const fut = useMemo(() => F.p50.map((_, s) => ({ t: qMs(p, o + s) + Q_MS / 2, s })), [F, p, o]);

  const y = useMemo(() => {
    const vis = (t: number) => t >= d0 - Q_MS && t <= d1 + Q_MS;
    const core: number[] = [];
    F.p10.forEach((_, s) => { if (vis(qMs(p, o + s) + Q_MS / 2)) core.push(F.p10[s], F.p90[s]); });
    past.forEach((d) => { if (d.spot !== null && vis(d.t)) core.push(d.spot - (simple ? 20 : 60), d.spot + (simple ? 20 : 60)); });
    if (core.length === 0) core.push(...F.p10, ...F.p90);
    const lo = Math.min(...core), hi = Math.max(...core), span = hi - lo;
    const real = past.filter((d) => d.y !== null && vis(d.t)).map((d) => d.y as number);
    const yMin = Math.max(Math.min(lo, ...real), lo - 0.8 * span);
    const yMax = Math.min(Math.max(hi, ...real), hi + 0.8 * span);
    return scaleLinear().domain([yMin, yMax]).range([M.t + PLOT_H, M.t]).nice(6).clamp(true);
  }, [F, past, d0, d1, p, o, simple]);

  const band = area<{ t: number; s: number }>().x((d) => x(d.t)).y0((d) => y(F.p10[d.s])).y1((d) => y(F.p90[d.s])).curve(curveMonotoneX);
  const med = line<{ t: number; s: number }>().x((d) => x(d.t)).y((d) => y(F.p50[d.s])).curve(curveMonotoneX);
  const step = (acc: (d: (typeof past)[number]) => number | null) =>
    line<(typeof past)[number]>().defined((d) => acc(d) !== null).x((d) => x(d.t)).y((d) => y(acc(d) as number)).curve(curveStepAfter);
  const realPts = past.filter((d) => d.t < T);
  const realLine = step((d) => d.y)([...realPts, ...(lastPub ? [{ ...lastPub, t: lastPub.t + Q_MS }] : [])]);
  const spotLine = step((d) => d.spot)(past);
  const plusLine = step((d) => (d.spot === null ? null : d.spot + 50))(past);
  const minusLine = step((d) => (d.spot === null ? null : d.spot - 50))(past);

  // time axis: every full hour, labels every second hour, the date at midnight
  const tstep = tickStep(d1 - d0);
  const minor = Math.max(Q_MS, tstep / 2);
  const ticks: { t: number; major: boolean }[] = [];
  for (let h = Math.ceil(d0 / minor) * minor; h <= d1; h += minor) ticks.push({ t: h, major: Math.round(h / minor) % Math.round(tstep / minor) === 0 });

  const cellX = (s: number) => [x(qMs(p, o + s)), x(qMs(p, o + s + 1))] as const;
  const focusRect = focus ? [cellX(focus.a)[0], cellX(focus.b)[1]] : null;
  const focusFill = focus?.kind === "spike_high" ? "hsl(var(--verm-soft))" : focus?.kind === "spike_low" ? "hsl(var(--teal-soft))" : "hsl(var(--accent))";

  const lastSpot = past[past.length - 1]?.spot ?? null;
  const roomLeft = xT - M.l > 170;
  const labX = roomLeft ? xT - 12 : M.l + 4;
  const labAnchor = roomLeft ? "end" : "start";
  const hs = hover !== null && hover >= o && hover < o + STEPS ? hover - o : null;
  const hp = hover !== null ? past.find((d) => Math.floor((d.t - p.t0) / Q_MS) === hover) : undefined;

  function onMove(e: React.PointerEvent<SVGSVGElement>) {
    const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    if (px < M.l || px > W - M.r) return setHover(null);
    setHover(Math.floor((x.invert(px) - p.t0) / Q_MS));
  }

  const summary = `${t(lang, "chartTitle")}. ${t(lang, "median")} ${fmt0(F.p50[0])}–${fmt0(F.p50[STEPS - 1])}, ${t(lang, "band")} ${fmt0(Math.min(...F.p10))}–${fmt0(Math.max(...F.p90))} ${t(lang, "eur")}.`;

  return (
    <div ref={wrap} className="relative w-full select-none">
      <div className="absolute right-0 top-0 z-[2]">
        <ZoomControls z={z} span={spanLabel(d1 - d0)}
          labels={{ in: t(lang, "zoomIn"), out: t(lang, "zoomOut"), reset: t(lang, "zoomReset") }} />
      </div>
      <svg ref={svgRef} width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}
        onPointerDown={dp.onPointerDown} onPointerUp={dp.onPointerUp} onDoubleClick={dp.onDoubleClick}
        onPointerMove={(e) => { if (!dp.onPointerMoveDrag(e)) onMove(e); }} onPointerLeave={() => setHover(null)}
        className={`block touch-none ${z.zoomed ? (dp.dragging ? "cursor-grabbing" : "cursor-grab") : ""}`}>
        <defs><clipPath id={`plot-${uid}`}><rect x={M.l} y={0} width={W - M.l - M.r} height={H} /></clipPath></defs>
        <g clipPath={`url(#plot-${uid})`}>
        {/* forecast period sits on the lighter sheet, as a projection does in a bulletin */}
        <rect x={xT} y={M.t} width={W - M.r - xT} height={axisY - M.t} fill="hsl(var(--sheet))" />
        {focusRect && <rect x={focusRect[0]} y={M.t} width={focusRect[1] - focusRect[0]} height={axisY - M.t} fill={focusFill} />}

        {/* y grid */}
        {y.ticks(6).map((v) => (
          <line key={v} x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} stroke="hsl(var(--rule))" strokeWidth={v === 0 ? 1.2 : 0.75} />
        ))}

        {/* spike thresholds and spot */}
        {!simple && <path d={plusLine ?? ""} fill="none" stroke="hsl(var(--verm))" strokeOpacity={0.55} strokeWidth={1} strokeDasharray="5 4" />}
        {!simple && <path d={minusLine ?? ""} fill="none" stroke="hsl(var(--teal))" strokeOpacity={0.55} strokeWidth={1} strokeDasharray="5 4" />}
        <path d={spotLine ?? ""} fill="none" stroke="hsl(var(--ink-2))" strokeWidth={1.4} strokeDasharray="1.5 3.5" strokeLinecap="round" />

        {/* the fan */}
        <g key={periodKey} className={reduced ? undefined : "fan-open"}>
          <path d={band(fut) ?? ""} fill="hsl(var(--fan-inner))" fillOpacity={0.62} />
          <path d={band(fut) ?? ""} fill="none" stroke="hsl(var(--fan-inner))" strokeWidth={1} />
          <path d={med(fut) ?? ""} fill="none" stroke="hsl(var(--bank))" strokeWidth={2.2} strokeDasharray="7 4" />
        </g>

        {/* realised, as published by the review time */}
        <path d={realLine ?? ""} fill="none" stroke="hsl(var(--ink))" strokeWidth={2} strokeLinejoin="round" />
        {lastPub && lastPub.y !== null && (
          <g>
            <circle cx={x(lastPub.t + Q_MS)} cy={y(lastPub.y)} r={3.2} fill="hsl(var(--ink))" />
            <text x={x(lastPub.t + Q_MS) - 6} y={M.t + PLOT_H - 8} textAnchor="end" className="fill-ink-3 text-[12px]">
              {t(lang, "published", { t: hhmm(lastPub.t + Q_MS, lang) })}
            </text>
          </g>
        )}

        </g>
        {y.ticks(6).map((v) => (
          <text key={v} x={M.l - 8} y={y(v)} dy="0.32em" textAnchor="end" className="num fill-ink-3 text-[12px]">{fmt0(v)}</text>
        ))}

        {/* right-hand labels */}
        {lastSpot !== null && (
          <g className="text-[12px]">
            {!simple && <text x={W - M.r + 8} y={y(lastSpot + 50)} dy="0.32em" className="fill-verm">{t(lang, "plus50")}</text>}
            <text x={W - M.r + 8} y={y(lastSpot)} dy="0.32em" className="fill-ink-2">{simple ? "" : t(lang, "spot")}</text>
            {!simple && <text x={W - M.r + 8} y={y(lastSpot - 50)} dy="0.32em" className="fill-teal">{t(lang, "minus50")}</text>}
          </g>
        )}

        <g clipPath={`url(#plot-${uid})`}>
        {/* review line */}
        <line x1={xT} x2={xT} y1={M.t - 14} y2={axisY} stroke="hsl(var(--bank))" strokeWidth={1.5} />
        <text x={xT + 6} y={M.t - 16} className="fill-bank text-[13px] font-semibold">{hhmm(T, lang)}</text>
        <text x={xT + 6 + 40} y={M.t - 16} className="fill-ink-3 text-[12px]">{t(lang, "now")}</text>

        {!simple && (<>
        {/* balancing direction ribbon */}
        <text x={labX} y={roomLeft ? ribY + RIB_H / 2 : ribY - 8} dy="0.32em" textAnchor={labAnchor} className="fill-ink-2 text-[13px] font-semibold">{t(lang, "direction")}</text>
        <g className="text-[11px]" opacity={roomLeft ? 1 : 0}>
          <rect x={xT - 150} y={ribY + RIB_H + 6} width={9} height={9} fill="hsl(var(--verm))" fillOpacity={0.8} />
          <text x={xT - 137} y={ribY + RIB_H + 14} className="fill-ink-3">{t(lang, "up")}</text>
          <rect x={xT - 104} y={ribY + RIB_H + 6} width={9} height={9} fill="hsl(var(--rule))" />
          <text x={xT - 91} y={ribY + RIB_H + 14} className="fill-ink-3">{t(lang, "none")}</text>
          <rect x={xT - 46} y={ribY + RIB_H + 6} width={9} height={9} fill="hsl(var(--teal))" fillOpacity={0.8} />
          <text x={xT - 33} y={ribY + RIB_H + 14} className="fill-ink-3">{t(lang, "down")}</text>
        </g>
        {F.pu.map((pu, s) => {
          const [x0, x1] = cellX(s);
          const w = Math.max(1, x1 - x0 - 1);
          const hu = pu * RIB_H, hn = F.pn[s] * RIB_H, hd = F.pd[s] * RIB_H;
          return (
            <g key={s} opacity={focus && (s < focus.a || s > focus.b) ? 0.45 : 1}>
              <rect x={x0} y={ribY} width={w} height={hu} fill="hsl(var(--verm))" fillOpacity={0.8} />
              <rect x={x0} y={ribY + hu} width={w} height={hn} fill="hsl(var(--rule))" />
              <rect x={x0} y={ribY + hu + hn} width={w} height={hd} fill="hsl(var(--teal))" fillOpacity={0.8} />
            </g>
          );
        })}

        {/* spike risk: high above the line, low below */}
        <text x={labX} y={roomLeft ? riskY + RISK_HALF / 2 : riskY - 8} dy="0.32em" textAnchor={labAnchor} className="fill-verm text-[13px] font-semibold">{t(lang, "highRisk")}</text>
        <text x={roomLeft ? labX : W - M.r - 4} y={roomLeft ? baseY + RISK_HALF / 2 : riskY - 8} dy="0.32em" textAnchor="end" className="fill-teal text-[13px] font-semibold">{t(lang, "lowRisk")}</text>
        <line x1={xT} x2={W - M.r} y1={baseY} y2={baseY} stroke="hsl(var(--ink-3))" strokeWidth={0.75} />
        <line x1={xT} x2={W - M.r} y1={baseY - 0.4 * RISK_HALF} y2={baseY - 0.4 * RISK_HALF} stroke="hsl(var(--verm))" strokeOpacity={0.5} strokeDasharray="3 3" />
        <line x1={xT} x2={W - M.r} y1={baseY + 0.5 * RISK_HALF} y2={baseY + 0.5 * RISK_HALF} stroke="hsl(var(--teal))" strokeOpacity={0.5} strokeDasharray="3 3" />
        <text x={W - M.r + 8} y={baseY - 0.4 * RISK_HALF} dy="0.32em" className="num fill-ink-3 text-[11px]">40 %</text>
        <text x={W - M.r + 8} y={baseY + 0.5 * RISK_HALF} dy="0.32em" className="num fill-ink-3 text-[11px]">50 %</text>
        {F.hi.map((hi, s) => {
          const [x0, x1] = cellX(s);
          const w = Math.max(1, x1 - x0 - 1);
          const dim = focus && (s < focus.a || s > focus.b) ? 0.45 : 1;
          return (
            <g key={s} opacity={dim}>
              <rect x={x0} y={baseY - hi * RISK_HALF} width={w} height={hi * RISK_HALF} fill="hsl(var(--verm))" fillOpacity={hi >= 0.4 ? 1 : 0.55} />
              <rect x={x0} y={baseY} width={w} height={F.lo[s] * RISK_HALF} fill="hsl(var(--teal))" fillOpacity={F.lo[s] >= 0.5 ? 1 : 0.55} />
            </g>
          );
        })}

        </>)}

        </g>
        {/* time axis: 2 h, 1 h, 30 or 15 min labels depending on the zoom */}
        {ticks.map(({ t: h, major }) => (
          <g key={h}>
            <line x1={x(h)} x2={x(h)} y1={axisY} y2={axisY + (major ? 6 : 3)} stroke="hsl(var(--ink-3))" />
            {major && <text x={x(h)} y={axisY + 18} textAnchor="middle" className="num fill-ink-3 text-[12px]">{hhmm(h, lang)}</text>}
            {major && hourOf(h) === 0 && new Date(h).getUTCMinutes() === 0 && <text x={x(h)} y={axisY + 32} textAnchor="middle" className="fill-ink-2 text-[12px] font-semibold">{dateShort(h, lang)}</text>}
          </g>
        ))}
        <line x1={M.l} x2={W - M.r} y1={axisY} y2={axisY} stroke="hsl(var(--ink-3))" strokeWidth={0.75} />

        {/* hover crosshair */}
        {hover !== null && (
          <line x1={x(qMs(p, hover) + Q_MS / 2)} x2={x(qMs(p, hover) + Q_MS / 2)} y1={M.t} y2={axisY}
            stroke="hsl(var(--ink))" strokeOpacity={0.35} strokeWidth={1} />
        )}
      </svg>

      {hover !== null && (hs !== null || hp) && (
        <div className="pointer-events-none absolute top-8 z-10 min-w-[188px] rounded-md border border-rule bg-sheet px-3 py-2 text-[13px] shadow-[0_6px_20px_-8px_rgba(20,34,51,0.35)]"
          style={{ left: Math.min(W - 200, Math.max(0, x(qMs(p, hover)) + 14)) }}>
          <div className="mb-1 font-semibold text-ink num">{hhmm(qMs(p, hover), lang)}–{hhmm(qMs(p, hover + 1), lang)}</div>
          <Row k={L.spot} v={hp?.spot ?? (hs !== null ? known(p.spot, p.spot_fu, hover, Tmin) : null)} />
          {hs === null && <Row k={t(lang, "realised")} v={hp?.y ?? null} />}
          {hs !== null && (
            <>
              <Row k={L.median} v={F.p50[hs]} strong />
              <div className="flex justify-between gap-4 text-ink-2"><span>{L.band}</span><span className="num">{fmt0(F.p10[hs])} – {fmt0(F.p90[hs])}</span></div>
              <div className="mt-1 flex justify-between gap-4 text-ink-2"><span>{t(lang, "up")} / {t(lang, "down")}</span><span className="num">{pct(F.pu[hs])} / {pct(F.pd[hs])}</span></div>
              <div className="flex justify-between gap-4 text-verm"><span>{t(lang, "highRisk")}</span><span className="num">{pct(F.hi[hs])}</span></div>
              <div className="flex justify-between gap-4 text-teal"><span>{t(lang, "lowRisk")}</span><span className="num">{pct(F.lo[hs])}</span></div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ k, v, strong }: { k: string; v: number | null | undefined; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-4 ${strong ? "text-ink font-semibold" : "text-ink-2"}`}>
      <span>{k}</span><span className="num">{v === null || v === undefined ? "–" : fmt0(v)}</span>
    </div>
  );
}

function spanLabel(ms: number) {
  const m = Math.round(ms / 60_000);
  const h = Math.floor(m / 60), r = m % 60;
  return h ? (r ? `${h} h ${r} min` : `${h} h`) : `${r} min`;
}

function labels(lang: Lang, simple: boolean) {
  return simple
    ? { median: t(lang, "sMedian"), band: t(lang, "sBand"), spot: t(lang, "sSpot") }
    : { median: t(lang, "median"), band: t(lang, "band"), spot: t(lang, "spot") };
}

export function ChartLegend({ lang, simple = false }: { lang: Lang; simple?: boolean }) {
  const L = labels(lang, simple);
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px] text-ink-2">
      <span className="inline-flex items-center gap-2"><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="hsl(var(--ink))" strokeWidth="2" /></svg>{t(lang, "realised")}</span>
      <span className="inline-flex items-center gap-2"><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="hsl(var(--bank))" strokeWidth="2.2" strokeDasharray="7 4" /></svg>{L.median}</span>
      <span className="inline-flex items-center gap-2"><svg width="22" height="10"><rect width="22" height="10" fill="hsl(var(--fan-inner))" fillOpacity="0.62" /></svg>{L.band}</span>
      <span className="inline-flex items-center gap-2"><svg width="22" height="8"><line x1="1" x2="21" y1="4" y2="4" stroke="hsl(var(--ink-2))" strokeWidth="1.4" strokeDasharray="1.5 3.5" strokeLinecap="round" /></svg>{L.spot}</span>
    </div>
  );
}

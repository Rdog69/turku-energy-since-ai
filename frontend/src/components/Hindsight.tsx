import { useEffect, useMemo, useRef, useState } from "react";
import { scaleLinear } from "d3-scale";
import { area, curveStepAfter, line } from "d3-shape";
import type { Period } from "@/data/types";
import { hindsight, reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { Q_MS, dateShort, hhmm, hourOf, type Lang } from "@/lib/time";
import { ZoomControls, tickStep, useBind, useDragPan, useZoom } from "@/lib/useZoom";

type Win = 24 | 168 | null;

export function Hindsight({ p, i, lang }: { p: Period; i: number; lang: Lang }) {
  const [win, setWin] = useState<Win>(168);
  const h = useMemo(() => hindsight(p, i, win), [p, i, win]);
  const start = reviewMs(p, 0);
  const tabs: [Win, string][] = [[24, t(lang, "h24")], [168, t(lang, "h7")], [null, t(lang, "hAll", { d: dateShort(start, lang) })]];
  const f0 = (v: number) => (Number.isFinite(v) ? Math.round(v).toString() : "–");
  const fp = (v: number) => (Number.isFinite(v) ? `${Math.round(v * 100)} %` : "–");

  return (
    <section aria-labelledby="hs-h">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-rule pb-2">
        <div>
          <h2 id="hs-h" className="text-[18px] font-bold text-ink">{t(lang, "hindsight")}</h2>
          <p className="text-[13px] text-ink-3">{t(lang, "hindsightHint")}</p>
        </div>
        <div role="tablist" aria-label={t(lang, "hindsight")} className="inline-flex rounded-md border border-rule bg-sheet p-0.5">
          {tabs.map(([w, label]) => (
            <button key={String(w)} role="tab" aria-selected={win === w} onClick={() => setWin(w)}
              className={`rounded-[4px] px-3 py-1.5 text-[13px] font-semibold transition-colors duration-150 ${win === w ? "bg-bank text-white" : "text-ink-2 hover:text-ink"}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {h.n === 0 ? (
        <p className="py-6 text-[14px] text-ink-2">{t(lang, "noHistory")}</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-y-4 py-4 md:grid-cols-4 md:divide-x md:divide-rule">
            <Figure label={t(lang, "mae")} value={`${f0(h.mae)}`} unit={t(lang, "eur")} sub={t(lang, "maeSub", { v: `${f0(h.maeSpot)} ${t(lang, "eur")}` })} />
            <Figure label={t(lang, "coverage")} value={fp(h.coverage)} sub={t(lang, "coverageSub")} />
            <Figure label={t(lang, "caught")} value={h.highN ? fp(h.highK / h.highN) : "–"} sub={t(lang, "caughtSub", { k: h.highK, n: h.highN })} />
            <Figure label={t(lang, "dirRight")} value={h.dirN ? fp(h.dirOk / h.dirN) : "–"} />
          </dl>
          <p className="mb-1 text-[13px] font-semibold text-ink-2">{t(lang, "hChart")}</p>
          <HindsightChart series={h.series} lang={lang} />
        </>
      )}
    </section>
  );
}

function Figure({ label, value, unit, sub }: { label: string; value: string; unit?: string; sub?: string }) {
  return (
    <div className="px-0 md:px-5 md:first:pl-0">
      <dt className="text-[13px] text-ink-2">{label}</dt>
      <dd className="mt-0.5">
        <span className="num text-[26px] font-semibold leading-none text-ink">{value}</span>
        {unit && <span className="ml-1 text-[13px] text-ink-3">{unit}</span>}
        {sub && <span className="num mt-1 block text-[12.5px] text-ink-3">{sub}</span>}
      </dd>
    </div>
  );
}

function HindsightChart({ series, lang }: { series: ReturnType<typeof hindsight>["series"]; lang: Lang }) {
  const wrap = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [W, setW] = useState(900);
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(480, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const H = 220, m = { l: 44, r: 12, t: 8, b: 26 };
  const first = series[0]?.t ?? 0, last = (series[series.length - 1]?.t ?? 1) + Q_MS;
  const z = useZoom([first, last], 2 * 3600_000, { l: m.l, r: m.r, w: W });
  useBind(svgRef, z);
  const dp = useDragPan(svgRef, z, W);
  if (series.length < 2) return <div ref={wrap} />;
  const [d0, d1] = z.domain;
  const x = scaleLinear().domain([d0, d1]).range([m.l, W - m.r]);
  const vis = series.filter((d) => d.t >= d0 - Q_MS && d.t <= d1);
  const vals = (vis.length > 4 ? vis : series).flatMap((d) => [d.p10, d.p90, d.y]).sort((a, b) => a - b);
  const lo = vals[Math.floor(vals.length * 0.01)], hi = vals[Math.min(vals.length - 1, Math.floor(vals.length * 0.99))];
  const y = scaleLinear().domain([lo, hi]).range([H - m.b, m.t]).nice(4).clamp(true);
  const band = area<(typeof series)[number]>().x((d) => x(d.t)).y0((d) => y(d.p10)).y1((d) => y(d.p90)).curve(curveStepAfter);
  const med = line<(typeof series)[number]>().x((d) => x(d.t)).y((d) => y(d.p50)).curve(curveStepAfter);
  const real = line<(typeof series)[number]>().x((d) => x(d.t)).y((d) => y(d.y)).curve(curveStepAfter);
  // axis: Finnish midnights when wide; hours (or 15 min) when zoomed in
  const HOUR = 3600_000;
  const span = d1 - d0;
  const step = span > 3 * 86400_000 ? 0 : tickStep(span);
  const marks: { t: number; day: boolean }[] = [];
  for (let h = Math.ceil(d0 / (step || HOUR)) * (step || HOUR); h < d1; h += step || HOUR) {
    const day = hourOf(h) === 0 && new Date(h).getUTCMinutes() === 0;
    if (day || step) marks.push({ t: h, day });
  }
  const hs = hover !== null ? series[hover] : null;
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (dp.onPointerMoveDrag(e)) return;
    const r = e.currentTarget.getBoundingClientRect();
    const tt = x.invert(((e.clientX - r.left) / r.width) * W);
    let k = 0;
    for (let j = 0; j < series.length; j++) if (series[j].t <= tt) k = j; else break;
    setHover(k);
  };
  return (
    <div ref={wrap} className="relative w-full select-none">
      <div className="mb-1 flex justify-end">
        <ZoomControls z={z} span={span >= 86400_000 ? `${Math.round(span / 86400_000)} d` : `${Math.round(span / HOUR)} h`}
          labels={{ in: t(lang, "zoomIn"), out: t(lang, "zoomOut"), reset: t(lang, "zoomReset") }} />
      </div>
      <svg ref={svgRef} width={W} height={H} role="img" aria-label={t(lang, "hChart")}
        onPointerDown={dp.onPointerDown} onPointerUp={dp.onPointerUp} onDoubleClick={dp.onDoubleClick}
        onPointerMove={onMove} onPointerLeave={() => setHover(null)}
        className={`block touch-none ${z.zoomed ? (dp.dragging ? "cursor-grabbing" : "cursor-grab") : ""}`}>
        <defs><clipPath id="hs-plot"><rect x={m.l} y={0} width={W - m.l - m.r} height={H} /></clipPath></defs>
        {y.ticks(4).map((v) => (
          <g key={v}>
            <line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} stroke="hsl(var(--rule))" strokeWidth={0.75} />
            <text x={m.l - 6} y={y(v)} dy="0.32em" textAnchor="end" className="num fill-ink-3 text-[11px]">{v}</text>
          </g>
        ))}
        <g clipPath="url(#hs-plot)">
          <path d={band(series) ?? ""} fill="hsl(var(--fan-inner))" fillOpacity={0.5} />
          <path d={med(series) ?? ""} fill="none" stroke="hsl(var(--bank))" strokeWidth={1.3} strokeDasharray="5 3" />
          <path d={real(series) ?? ""} fill="none" stroke="hsl(var(--ink))" strokeWidth={1.2} />
          {marks.map(({ t: d, day }) => (
            <g key={d}>
              <line x1={x(d)} x2={x(d)} y1={m.t} y2={H - m.b} stroke="hsl(var(--rule))" strokeWidth={day ? 1 : 0.5} />
              <text x={x(d) + 4} y={H - 8} className={`num text-[11px] ${day ? "fill-ink-2 font-semibold" : "fill-ink-3"}`}>
                {day ? dateShort(d, lang) : hhmm(d, lang)}
              </text>
            </g>
          ))}
          {hs && <line x1={x(hs.t + Q_MS / 2)} x2={x(hs.t + Q_MS / 2)} y1={m.t} y2={H - m.b} stroke="hsl(var(--ink))" strokeOpacity={0.35} />}
        </g>
      </svg>
      {hs && (
        <div className="pointer-events-none absolute top-10 z-10 rounded-md border border-rule bg-sheet px-3 py-2 text-[12.5px] shadow-[0_6px_20px_-8px_rgba(20,34,51,0.35)]"
          style={{ left: Math.min(W - 190, Math.max(0, x(hs.t) + 12)) }}>
          <div className="num font-semibold text-ink">{dateShort(hs.t, lang)} {hhmm(hs.t, lang)}</div>
          <div className="num flex justify-between gap-4 text-ink-2"><span>{t(lang, "realised")}</span><span>{Math.round(hs.y)}</span></div>
          <div className="num flex justify-between gap-4 text-bank"><span>{t(lang, "median")}</span><span>{Math.round(hs.p50)}</span></div>
          <div className="num flex justify-between gap-4 text-ink-2"><span>{t(lang, "band")}</span><span>{Math.round(hs.p10)} – {Math.round(hs.p90)}</span></div>
        </div>
      )}
    </div>
  );
}


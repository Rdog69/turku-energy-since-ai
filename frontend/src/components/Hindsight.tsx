import { useEffect, useMemo, useRef, useState } from "react";
import { scaleLinear } from "d3-scale";
import { area, curveStepAfter, line } from "d3-shape";
import type { Period } from "@/data/types";
import { hindsight, reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { Q_MS, dateShort, hourOf, type Lang } from "@/lib/time";

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
  const [W, setW] = useState(900);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(480, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  if (series.length < 2) return <div ref={wrap} />;
  const H = 180, m = { l: 44, r: 12, t: 8, b: 24 };
  const x = scaleLinear().domain([series[0].t, series[series.length - 1].t + Q_MS]).range([m.l, W - m.r]);
  const vals = series.flatMap((d) => [d.p10, d.p90, d.y]).sort((a, b) => a - b);
  const lo = vals[Math.floor(vals.length * 0.01)], hi = vals[Math.floor(vals.length * 0.99)];
  const y = scaleLinear().domain([lo, hi]).range([H - m.b, m.t]).nice(4).clamp(true);
  const band = area<(typeof series)[number]>().x((d) => x(d.t)).y0((d) => y(d.p10)).y1((d) => y(d.p90)).curve(curveStepAfter);
  const med = line<(typeof series)[number]>().x((d) => x(d.t)).y((d) => y(d.p50)).curve(curveStepAfter);
  const real = line<(typeof series)[number]>().x((d) => x(d.t)).y((d) => y(d.y)).curve(curveStepAfter);
  const days: number[] = [];          // Finnish midnights
  const HOUR = 3600_000;
  for (let h = Math.ceil(series[0].t / HOUR) * HOUR; h < series[series.length - 1].t; h += HOUR) if (hourOf(h) === 0) days.push(h);
  return (
    <div ref={wrap} className="w-full">
      <svg width={W} height={H} role="img" aria-label={t(lang, "hChart")}>
        {y.ticks(4).map((v) => (
          <g key={v}>
            <line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} stroke="hsl(var(--rule))" strokeWidth={0.75} />
            <text x={m.l - 6} y={y(v)} dy="0.32em" textAnchor="end" className="num fill-ink-3 text-[11px]">{v}</text>
          </g>
        ))}
        <path d={band(series) ?? ""} fill="hsl(var(--fan-inner))" fillOpacity={0.5} />
        <path d={med(series) ?? ""} fill="none" stroke="hsl(var(--bank))" strokeWidth={1.3} strokeDasharray="5 3" />
        <path d={real(series) ?? ""} fill="none" stroke="hsl(var(--ink))" strokeWidth={1.2} />
        {days.map((d) => (
          <g key={d}>
            <line x1={x(d)} x2={x(d)} y1={m.t} y2={H - m.b} stroke="hsl(var(--rule))" />
            <text x={x(d) + 4} y={H - 8} className="fill-ink-3 text-[11px]">{dateShort(d, lang)}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

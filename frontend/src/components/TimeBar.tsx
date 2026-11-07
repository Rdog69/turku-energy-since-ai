import { useMemo, useRef } from "react";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Clock, Pause, Play } from "lucide-react";
import * as Slider from "@radix-ui/react-slider";
import type { Period } from "@/data/types";
import { alertWeights, reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { dateShort, dayLong, hhmm, hourOf, type Lang } from "@/lib/time";

export function TimeBar({ p, i, setI, lang, playing, setPlaying, offset = 0, compact = false }: {
  p: Period; i: number; setI: (i: number) => void; lang: Lang; playing: boolean; setPlaying: (v: boolean) => void;
  /** ms past forecast hour i (the Overview page scrolls in 15-minute steps) */
  offset?: number; compact?: boolean;
}) {
  const n = p.origins.length;
  const T = reviewMs(p, i);
  const now = T + offset;
  const cutoff = p.t0 + p.cutoff[i] * 60_000;
  const age = Math.round((now - cutoff) / 60_000);
  const weights = useMemo(() => alertWeights(p), [p]);
  const maxW = Math.max(1, ...weights);
  const go = (d: number) => setI(Math.max(0, Math.min(n - 1, i + d)));

  const days = useMemo(() => {
    const out: { k: number; ms: number }[] = [];
    for (let k = 0; k < n; k++) if (hourOf(reviewMs(p, k)) === 0) out.push({ k, ms: reviewMs(p, k) });
    return out;
  }, [p, n]);

  const btn = "inline-flex h-10 w-10 items-center justify-center rounded-md border border-rule bg-sheet text-ink-2 transition-[color,transform] duration-150 ease-out hover:text-bank active:scale-[0.96] disabled:opacity-40";

  return (
    <section aria-label={t(lang, "reviewTime")} className={compact ? "" : "border-b border-rule pb-4"}>
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
        <div>
          {!compact && <p className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-ink-2"><Clock size={14} strokeWidth={2} />{t(lang, "reviewTime")}</p>}
          <p className={`num font-bold leading-tight text-ink ${compact ? "text-[22px]" : "text-[30px]"}`}>
            <span className="capitalize">{dayLong(now, lang)}</span>{" "}
            <span className="text-bank">{hhmm(now, lang)}</span>
          </p>
          <p className="num text-[13.5px] text-ink-2">
            {t(lang, "made")} {hhmm(T, lang)}, {t(lang, "newest", { t: hhmm(cutoff, lang), m: age })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className={btn} onClick={() => go(-24)} disabled={i === 0} aria-label={t(lang, "prevDay")} title={t(lang, "prevDay")}><ChevronsLeft size={18} strokeWidth={1.75} /></button>
          <button type="button" className={btn} onClick={() => go(-1)} disabled={i === 0} aria-label={t(lang, "prevHour")} title={t(lang, "prevHour")}><ChevronLeft size={18} strokeWidth={1.75} /></button>
          <button type="button" onClick={() => setPlaying(!playing)} aria-pressed={playing}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-bank px-4 text-[14px] font-semibold text-white transition-transform duration-150 ease-out active:scale-[0.96]">
            {playing ? <Pause size={16} strokeWidth={2} /> : <Play size={16} strokeWidth={2} />}
            {playing ? t(lang, "pause") : t(lang, "play")}
          </button>
          <button type="button" className={btn} onClick={() => go(1)} disabled={i === n - 1} aria-label={t(lang, "nextHour")} title={t(lang, "nextHour")}><ChevronRight size={18} strokeWidth={1.75} /></button>
          <button type="button" className={btn} onClick={() => go(24)} disabled={i === n - 1} aria-label={t(lang, "nextDay")} title={t(lang, "nextDay")}><ChevronsRight size={18} strokeWidth={1.75} /></button>
        </div>
      </div>

      <div className={compact ? "mt-3" : "mt-4"}>
        {/* the full-page view keeps its hour-by-hour bars; the Overview page has just the line */}
        {!compact && (
          <svg className="block h-[30px] w-full" viewBox={`0 0 ${n} 30`} preserveAspectRatio="none" aria-hidden>
            {weights.map((w, k) => w > 0 && (
              <rect key={k} x={k} y={30 - (w / maxW) * 28} width={0.85} height={(w / maxW) * 28}
                fill={k === i ? "hsl(var(--bank))" : "hsl(var(--ink-3))"} fillOpacity={k === i ? 1 : 0.45} />
            ))}
          </svg>
        )}
        <Slider.Root value={[i]} min={0} max={n - 1} step={1} onValueChange={([v]) => { setPlaying(false); setI(v); }}
          aria-label={t(lang, "timeline")} className="relative flex h-5 w-full touch-none select-none items-center">
          <Slider.Track className="relative h-px w-full grow bg-ink-3/45">
            <Slider.Range className="absolute h-px bg-bank" />
          </Slider.Track>
          <Slider.Thumb className="block h-3 w-3 rounded-full bg-bank ring-4 ring-bank/15 transition-[box-shadow] duration-150 hover:ring-bank/25 focus-visible:outline-none focus-visible:ring-bank/40" />
        </Slider.Root>
        {!compact && (
          <div className="relative h-4">
            {days.filter((_, k) => k % 2 === 0).map((d, j) => (
              <span key={d.k} className={`num absolute -translate-x-1/2 text-[11.5px] text-ink-3 ${j % 2 ? "hidden md:inline" : ""}`} style={{ left: `${(d.k / (n - 1)) * 100}%` }}>
                {dateShort(d.ms, lang)}
              </span>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

/**
 * The whole period under the graph: hours with something worth checking as faint bars, the part the graph shows as
 * a half-transparent window. Click or drag on it to travel.
 */
export function PeriodStrip({ p, i, win, onJump, lang }: {
  p: Period; i: number; win: [number, number]; onJump: (i: number) => void; lang: Lang;
}) {
  const n = p.origins.length;
  const weights = useMemo(() => alertWeights(p), [p]);
  const maxW = Math.max(1, ...weights);
  const t0 = reviewMs(p, 0), t1 = reviewMs(p, n - 1);
  const fr = (ms: number) => Math.max(0, Math.min(1, (ms - t0) / (t1 - t0)));
  const box = { l: fr(win[0]) * 100, w: Math.max(0.8, (fr(win[1]) - fr(win[0])) * 100) };
  const days = useMemo(() => {
    const out: { k: number; ms: number }[] = [];
    for (let k = 0; k < n; k++) if (hourOf(reviewMs(p, k)) === 0) out.push({ k, ms: reviewMs(p, k) });
    return out;
  }, [p, n]);
  const ref = useRef<HTMLDivElement>(null);
  const down = useRef(false);
  const at = (clientX: number) => {
    const r = ref.current!.getBoundingClientRect();
    onJump(Math.round(Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * (n - 1)));
  };
  return (
    <div className="mt-1 pl-[118px] pr-[92px]">
      <div ref={ref} role="slider" aria-label={t(lang, "timeline")} aria-valuemin={0} aria-valuemax={n - 1} aria-valuenow={i} tabIndex={-1}
        className="relative h-[30px] cursor-pointer touch-none select-none rounded-[4px] bg-paper"
        onPointerDown={(e) => { down.current = true; (e.currentTarget as Element).setPointerCapture(e.pointerId); at(e.clientX); }}
        onPointerMove={(e) => { if (down.current) at(e.clientX); }}
        onPointerUp={() => { down.current = false; }}>
        <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${n} 30`} preserveAspectRatio="none" aria-hidden>
          {weights.map((w, k) => w > 0 && (
            <rect key={k} x={k} y={30 - (w / maxW) * 26} width={0.85} height={(w / maxW) * 26} fill="hsl(var(--ink-3))" fillOpacity={0.4} />
          ))}
        </svg>
        <span aria-hidden className="pointer-events-none absolute inset-y-0 rounded-[4px] border border-bank/60 bg-bank/[0.12]"
          style={{ left: `${box.l}%`, width: `${box.w}%` }} />
      </div>
      <div className="relative h-4">
        {days.filter((_, k) => k % 2 === 0).map((d, j) => (
          <span key={d.k} className={`num absolute -translate-x-1/2 pt-0.5 text-[11px] text-ink-3 ${j % 2 ? "hidden md:inline" : ""}`} style={{ left: `${(d.k / (n - 1)) * 100}%` }}>
            {dateShort(d.ms, lang)}
          </span>
        ))}
      </div>
    </div>
  );
}

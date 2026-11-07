import { useMemo, useRef, useState } from "react";
import type { Period } from "@/data/types";
import { alertWeights, reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { dateShort, hourOf, type Lang } from "@/lib/time";
import { BACK } from "./TimeChart";

/**
 * A standard timeline slider for the whole replay period: track, progress up to "now", one round thumb.
 * Click or drag anywhere to move "now"; the thumb follows the graph's glide. A faint band marks the hours the
 * graph shows, and faint ticks above the track mark hours worth checking.
 */
export function PeriodStrip({ p, view, lang, onJump }: {
  p: Period; tNow: number; view: [number, number]; lang: Lang;
  onPan: (ms: number) => void; onJump: (ms: number) => void;
}) {
  const n = p.origins.length;
  const t0 = reviewMs(p, 0), t1 = reviewMs(p, n - 1) + 45 * 60_000;
  const span = t1 - t0;
  const weights = useMemo(() => alertWeights(p), [p]);
  const maxW = Math.max(1, ...weights);
  const ref = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const down = useRef(false);   // a ref, so the first move events after the press already see it

  const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
  const fr = (ms: number) => clamp01((ms - t0) / span);
  const now = fr(view[0] + BACK * (view[1] - view[0]));   // glides with the graph
  const l = fr(view[0]), r = fr(view[1]);
  const days = useMemo(() => {
    const out: number[] = [];
    for (let k = 0; k < n; k++) if (hourOf(reviewMs(p, k)) === 0) out.push(reviewMs(p, k));
    return out;
  }, [p, n]);
  const msAt = (clientX: number) => {
    const rc = ref.current!.getBoundingClientRect();
    return t0 + clamp01((clientX - rc.left) / rc.width) * span;
  };

  return (
    <div className="select-none px-2">
      <div ref={ref} aria-hidden
        className={`group relative h-9 ${dragging ? "cursor-grabbing" : "cursor-pointer"}`}
        onPointerDown={(e) => {
          if (e.button !== 0) return;
          down.current = true;
          setDragging(true);
          ref.current?.setPointerCapture(e.pointerId);
          onJump(msAt(e.clientX));
        }}
        onPointerMove={(e) => { if (down.current) onJump(msAt(e.clientX)); }}
        onPointerUp={() => { down.current = false; setDragging(false); }}
        onPointerCancel={() => { down.current = false; setDragging(false); }}>
        {/* hours worth checking, faint */}
        <svg className="absolute inset-x-0 top-0 h-3 w-full" viewBox={`0 0 ${n} 10`} preserveAspectRatio="none">
          {weights.map((w, k) => w > 0 && <rect key={k} x={k} y={10 - (w / maxW) * 10} width={0.9} height={(w / maxW) * 10} fill="hsl(var(--ink-3))" fillOpacity={0.3} />)}
        </svg>
        {/* track, the hours on screen, progress up to now */}
        <span className="absolute inset-x-0 top-[22px] h-1 -translate-y-1/2 rounded-full bg-rule" />
        <span className="absolute top-[22px] h-2 -translate-y-1/2 rounded-full bg-bank/15" style={{ left: `${l * 100}%`, width: `${Math.max(0.5, (r - l) * 100)}%` }} />
        <span className="absolute left-0 top-[22px] h-1 -translate-y-1/2 rounded-full bg-bank/70" style={{ width: `${now * 100}%` }} />
        {days.map((ms) => <span key={ms} className="absolute top-[22px] h-2.5 w-px -translate-y-1/2 bg-ink-3/30" style={{ left: `${fr(ms) * 100}%` }} />)}
        {/* thumb */}
        <span role="slider" tabIndex={0} aria-label={t(lang, "timeline")} aria-valuemin={0} aria-valuemax={n - 1} aria-valuenow={Math.round(now * (n - 1))}
          className={`absolute top-[22px] h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bank bg-sheet shadow-[0_1px_4px_rgba(11,60,106,0.35)] transition-transform duration-150 group-hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bank focus-visible:ring-offset-2 ${dragging ? "scale-110" : ""}`}
          style={{ left: `${now * 100}%` }} />
      </div>
      <div className="relative h-4">
        {days.filter((_, j) => j % 2 === 0).map((ms, j) => (
          <span key={ms} className={`num absolute -translate-x-1/2 whitespace-nowrap text-[11px] text-ink-3 ${j % 2 ? "hidden md:inline" : ""}`} style={{ left: `${fr(ms) * 100}%` }}>
            {dateShort(ms, lang)}
          </span>
        ))}
      </div>
    </div>
  );
}

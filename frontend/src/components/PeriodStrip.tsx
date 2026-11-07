import { useMemo, useRef, useState } from "react";
import type { Period } from "@/data/types";
import { reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { dateShort, hourOf, type Lang } from "@/lib/time";

/**
 * The whole replay period as one slim track, with a translucent window for the hours the graph shows.
 * Drag the window to move through time; click the track to glide there.
 */
export function PeriodStrip({ p, tNow, view, lang, onPan, onJump }: {
  p: Period; tNow: number; view: [number, number]; lang: Lang;
  onPan: (ms: number) => void; onJump: (ms: number) => void;
}) {
  const n = p.origins.length;
  const t0 = reviewMs(p, 0), t1 = reviewMs(p, n - 1) + 3600_000;
  const span = t1 - t0;
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const fr = (ms: number) => (ms - t0) / span;
  const l = Math.max(0, fr(view[0])), r = Math.min(1, fr(view[1]));
  const now = fr(tNow);
  const days = useMemo(() => {
    const out: number[] = [];
    for (let k = 0; k < n; k++) if (hourOf(reviewMs(p, k)) === 0) out.push(reviewMs(p, k));
    return out;
  }, [p, n]);
  const width = () => ref.current?.getBoundingClientRect().width ?? 1;
  const msAt = (clientX: number) => {
    const rc = ref.current!.getBoundingClientRect();
    return t0 + Math.max(0, Math.min(1, (clientX - rc.left) / rc.width)) * span;
  };

  return (
    <div className="select-none">
      <div ref={ref}
        className={`relative h-5 ${dragging ? "cursor-grabbing" : "cursor-pointer"}`}
        onPointerMove={(e) => { if (drag.current) { onPan(((e.clientX - drag.current.x) / width()) * span); drag.current.x = e.clientX; } }}
        onPointerUp={() => { drag.current = null; setDragging(false); }}
        onPointerDown={(e) => { if (e.button === 0 && !drag.current) onJump(msAt(e.clientX)); }}
        aria-hidden>
        <span className="absolute inset-x-0 top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-rule" />
        {days.map((ms) => <span key={ms} className="absolute top-1/2 h-[7px] w-px -translate-y-1/2 bg-ink-3/40" style={{ left: `${fr(ms) * 100}%` }} />)}
        <div role="slider" tabIndex={0} aria-label={t(lang, "timeline")} aria-valuemin={0} aria-valuemax={n - 1} aria-valuenow={Math.round(now * (n - 1))}
          className={`absolute inset-y-0 rounded-full border border-bank/35 bg-bank/15 transition-colors duration-150 hover:bg-bank/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bank ${dragging ? "cursor-grabbing bg-bank/25" : "cursor-grab"}`}
          style={{ left: `${l * 100}%`, width: `${Math.max(0.8, (r - l) * 100)}%` }}
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            e.stopPropagation();
            drag.current = { x: e.clientX };
            setDragging(true);
            ref.current?.setPointerCapture(e.pointerId);
          }}>
          <span className="pointer-events-none absolute inset-y-[3px] w-[2px] rounded-full bg-bank" style={{ left: `${((now - l) / Math.max(1e-6, r - l)) * 100}%` }} />
        </div>
      </div>
      <div className="relative mt-0.5 h-4">
        {days.filter((_, j) => j % 3 === 0).map((ms) => (
          <span key={ms} className="num absolute -translate-x-1/2 whitespace-nowrap text-[11px] text-ink-3" style={{ left: `${fr(ms) * 100}%` }}>
            {dateShort(ms, lang)}
          </span>
        ))}
      </div>
    </div>
  );
}

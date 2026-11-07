import { useMemo, useRef, useState } from "react";
import type { Period } from "@/data/types";
import { alertWeights, reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { Q_MS, dateShort, hhmm, hourOf, type Lang } from "@/lib/time";
import { PLOT_MARGIN } from "./TimeChart";

const H_MS = 3600_000;

/**
 * Frank's period strip (from his version d2a0d19): the whole period, hour by hour, with a half-transparent box for the
 * window the graph shows. Drag the box, or press anywhere on the strip to centre the window there and keep dragging.
 * Every move goes through the same 15-minute steps as scrolling the graph. Lined up with the graph's plot area.
 */
export function PeriodStrip({ p, i, now: nowMs, view, lang, onPan, onPanEnd, onJump }: {
  p: Period; i: number; now: number; view: [number, number]; lang: Lang;
  onPan: (ms: number) => void; onPanEnd: () => void; onJump: (ms: number) => void;
}) {
  const n = p.origins.length;
  const t0 = reviewMs(p, 0), span = n * H_MS;          // forecast hour k fills [k/n, (k+1)/n] of the strip
  const weights = useMemo(() => alertWeights(p), [p]);
  const maxW = Math.max(1, ...weights);
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef<number | null>(null);            // last pointer x while dragging
  const [dragging, setDragging] = useState(false);
  const [hoverX, setHoverX] = useState<number | null>(null);

  const fr = (ms: number) => (ms - t0) / span;
  const l = fr(view[0]), r = fr(view[1]);
  const box = { l: Math.max(0, l), r: Math.min(1, r) };
  const now = fr(nowMs);
  const days = useMemo(() => {
    const out: number[] = [];
    for (let k = 0; k < n; k++) if (hourOf(reviewMs(p, k)) === 0) out.push(k);
    return out;
  }, [p, n]);

  const rect = () => ref.current!.getBoundingClientRect();
  const msAt = (clientX: number) => {
    const rc = rect();
    return t0 + Math.max(0, Math.min(1, (clientX - rc.left) / rc.width)) * span;
  };
  const end = () => { if (drag.current !== null) { drag.current = null; setDragging(false); onPanEnd(); } };
  const pctAt = (k: number) => (k / n) * 100;
  const hoverMs = hoverX !== null && ref.current ? msAt(rect().left + hoverX) : null;

  return (
    <div className="flex select-none items-start">
      <div className="hidden shrink-0 pr-3 pt-[13px] text-[13px] font-semibold leading-none text-ink-2 sm:block" style={{ width: PLOT_MARGIN.l }}>
        {t(lang, "oPeriod")}
      </div>
      <div className="min-w-0 flex-1">
        <div ref={ref}
          className={`relative h-10 touch-none overflow-hidden rounded-md border border-rule bg-paper ${dragging ? "cursor-grabbing" : "cursor-pointer"}`}
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            const rc = rect(), x = e.clientX - rc.left;
            // outside the box: centre the window there first; either way keep dragging from here
            if (x < box.l * rc.width || x > box.r * rc.width) onJump(msAt(e.clientX));
            drag.current = e.clientX;
            setDragging(true);
            ref.current?.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            setHoverX(e.clientX - rect().left);
            if (drag.current !== null) { onPan(((e.clientX - drag.current) / rect().width) * span); drag.current = e.clientX; }
          }}
          onPointerUp={end} onPointerCancel={end}
          onPointerLeave={() => setHoverX(null)}>
          {/* hours worth checking: taller = more to check; the hours inside the window in brand blue */}
          <svg className="absolute inset-x-0 bottom-0 h-8 w-full" viewBox={`0 0 ${n} 32`} preserveAspectRatio="none" aria-hidden>
            {weights.map((w, k) => {
              if (w <= 0) return null;
              const inWin = (k + 1) / n > l && k / n < r;
              return <rect key={k} x={k + 0.08} y={32 - (w / maxW) * 30} width={0.84} height={(w / maxW) * 30}
                fill={inWin ? "hsl(var(--bank))" : "hsl(var(--ink-3))"} fillOpacity={inWin ? 0.75 : 0.32} />;
            })}
          </svg>
          {days.map((k) => <span key={k} className="pointer-events-none absolute inset-y-0 w-px bg-rule" style={{ left: `${pctAt(k)}%` }} />)}

          {hoverX !== null && !dragging && <span className="pointer-events-none absolute inset-y-0 w-px bg-bank/50" style={{ left: hoverX }} />}

          {/* the window the graph shows (half-transparent box) and "now" inside it */}
          <div role="slider" tabIndex={0} aria-label={t(lang, "timeline")}
            aria-valuemin={0} aria-valuemax={n - 1} aria-valuenow={i} aria-valuetext={`${dateShort(nowMs, lang)} ${hhmm(nowMs, lang)}`}
            onKeyDown={(e) => {
              const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
              if (!d) return;
              e.preventDefault();
              onPan(d * (e.shiftKey ? H_MS : Q_MS));
              onPanEnd();
            }}
            className={`absolute inset-y-[3px] rounded-[5px] border-2 border-bank bg-bank/[0.08] shadow-[0_2px_8px_-3px_rgba(11,60,106,0.45)] transition-colors duration-150 hover:bg-bank/[0.14] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bank focus-visible:ring-offset-2 ${dragging ? "cursor-grabbing bg-bank/[0.16]" : "cursor-grab"}`}
            style={{ left: `${box.l * 100}%`, width: `max(10px, ${(box.r - box.l) * 100}%)` }} />
          {now >= 0 && now <= 1 && <span className="pointer-events-none absolute inset-y-[3px] w-[2px] -translate-x-1/2 bg-bank" style={{ left: `${now * 100}%` }} />}
        </div>

        {/* dates, every other day; the first and last kept inside the strip. While hovering: the time under the pointer */}
        <div className="relative mt-1 h-4">
          {days.filter((_, j) => j % 2 === 0).map((k, j) => {
            const x = pctAt(k);
            const shift = x < 2 ? "" : x > 98 ? "-translate-x-full" : "-translate-x-1/2";
            return (
              <span key={k} className={`num absolute whitespace-nowrap text-[11.5px] text-ink-3 ${shift} ${j % 2 ? "hidden md:inline" : ""}`} style={{ left: `${x}%` }}>
                {dateShort(reviewMs(p, k), lang)}
              </span>
            );
          })}
          {hoverMs !== null && hoverX !== null && !dragging && (
            <span className="num pointer-events-none absolute z-10 -translate-x-1/2 whitespace-nowrap rounded bg-bank px-1.5 text-[11.5px] font-semibold leading-4 text-white"
              style={{ left: Math.max(36, Math.min(rect().width - 36, hoverX)) }}>
              {dateShort(hoverMs, lang)} {hhmm(Math.floor(hoverMs / Q_MS) * Q_MS, lang)}
            </span>
          )}
        </div>
      </div>
      <div className="hidden shrink-0 sm:block" style={{ width: PLOT_MARGIN.r }} />
    </div>
  );
}

import { useMemo, useRef, useState } from "react";
import { GripVertical } from "lucide-react";
import type { Period } from "@/data/types";
import { alertWeights, reviewMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { dateShort, hourOf, type Lang } from "@/lib/time";

/**
 * The whole period as a strip: how much was worth checking hour by hour, and a box for the window the graph shows.
 * Drag the box to move through time; click anywhere else to glide there. The box is the handle (no separate knob).
 */
export function PeriodStrip({ p, tNow, view, lang, onPan, onJump }: {
  p: Period; tNow: number; view: [number, number]; lang: Lang;
  onPan: (ms: number) => void; onJump: (ms: number) => void;
}) {
  const n = p.origins.length;
  const t0 = reviewMs(p, 0), t1 = reviewMs(p, n - 1) + 3600_000;
  const span = t1 - t0;
  const weights = useMemo(() => alertWeights(p), [p]);
  const maxW = Math.max(1, ...weights);
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [hoverX, setHoverX] = useState<number | null>(null);

  const fr = (ms: number) => (ms - t0) / span;
  const l = Math.max(0, fr(view[0])), r = Math.min(1, fr(view[1]));
  const now = fr(tNow);
  const days = useMemo(() => {
    const out: number[] = [];
    for (let k = 0; k < n; k++) if (hourOf(reviewMs(p, k)) === 0) out.push(k);
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
        className={`group relative h-8 overflow-hidden rounded-md bg-paper/80 ${dragging ? "cursor-grabbing" : "cursor-pointer"}`}
        onPointerMove={(e) => {
          const rc = ref.current!.getBoundingClientRect();
          setHoverX(e.clientX - rc.left);
          if (drag.current) { onPan(((e.clientX - drag.current.x) / width()) * span); drag.current.x = e.clientX; }
        }}
        onPointerLeave={() => setHoverX(null)}
        onPointerUp={() => { drag.current = null; setDragging(false); }}
        onPointerDown={(e) => { if (e.button === 0 && !drag.current) onJump(msAt(e.clientX)); }}
        aria-hidden>
        {/* hours worth checking: taller and darker = more to check */}
        <svg className="absolute inset-x-0 bottom-0 h-7 w-full" viewBox={`0 0 ${n} 36`} preserveAspectRatio="none">
          {weights.map((w, k) => w > 0 && (
            <rect key={k} x={k} y={36 - (w / maxW) * 34} width={0.9} height={(w / maxW) * 34} fill="hsl(var(--ink-3))" fillOpacity={0.22} />
          ))}
        </svg>
        {days.map((k) => <span key={k} className="absolute inset-y-0 w-px bg-rule/70" style={{ left: `${fr(reviewMs(p, k)) * 100}%` }} />)}

        {/* hover guide */}
        {hoverX !== null && !dragging && <span className="pointer-events-none absolute inset-y-0 w-px bg-bank/40" style={{ left: hoverX }} />}

        {/* the window the graph shows */}
        <div role="slider" tabIndex={0} aria-label={t(lang, "timeline")} aria-valuemin={0} aria-valuemax={n - 1} aria-valuenow={Math.round(now * (n - 1))}
          className={`absolute inset-y-0.5 flex items-center justify-center rounded-[5px] border border-bank/50 bg-bank/[0.08] transition-colors duration-150 hover:border-bank hover:bg-bank/[0.14] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bank ${dragging ? "cursor-grabbing border-bank bg-bank/[0.16]" : "cursor-grab"}`}
          style={{ left: `${l * 100}%`, width: `${Math.max(1.2, (r - l) * 100)}%` }}
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            e.stopPropagation();
            drag.current = { x: e.clientX };
            setDragging(true);
            ref.current?.setPointerCapture(e.pointerId);
          }}>
          <GripVertical size={12} strokeWidth={2} className="text-bank/50" />
          {/* now, inside the box */}
          <span className="pointer-events-none absolute inset-y-1 w-[2px] rounded-full bg-bank" style={{ left: `${((now - l) / Math.max(1e-6, r - l)) * 100}%` }} />
        </div>
      </div>
      <div className="relative mt-1 h-4">
        {days.filter((_, j) => j % 2 === 0).map((k, j) => (
          <span key={k} className={`num absolute -translate-x-1/2 whitespace-nowrap text-[11px] text-ink-3 ${j % 2 ? "hidden md:inline" : ""}`} style={{ left: `${fr(reviewMs(p, k)) * 100}%` }}>
            {dateShort(reviewMs(p, k), lang)}
          </span>
        ))}
      </div>
    </div>
  );
}

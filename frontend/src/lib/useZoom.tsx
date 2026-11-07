import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { Maximize2, ZoomIn, ZoomOut } from "lucide-react";

/**
 * Zoom and pan over a time axis. The window is stored as fractions [a, b] of the full domain, so it stays put
 * relative to the review time while the user travels through time.
 * Pinch or ctrl/cmd + wheel zooms at the pointer, a horizontal wheel or a drag pans, a double-click zooms in.
 */
export function useZoom(full: [number, number], minSpan: number, plot: { l: number; r: number; w: number }) {
  const [frac, setFrac] = useState<[number, number]>([0, 1]);
  const fullSpan = full[1] - full[0];
  const domain: [number, number] = [full[0] + frac[0] * fullSpan, full[0] + frac[1] * fullSpan];
  const minF = Math.min(1, minSpan / fullSpan);
  const zoomed = frac[0] > 0 || frac[1] < 1;

  const zoomAt = useCallback((center: number, factor: number) => {
    setFrac(([a, b]) => {
      const span = Math.min(1, Math.max(minF, (b - a) * factor));
      let na = center - (center - a) * (span / (b - a));
      na = Math.max(0, Math.min(1 - span, na));
      return [na, na + span];
    });
  }, [minF]);
  const pan = useCallback((d: number) => {
    setFrac(([a, b]) => {
      const span = b - a;
      const na = Math.max(0, Math.min(1 - span, a + d));
      return [na, na + span];
    });
  }, []);
  const reset = useCallback(() => setFrac([0, 1]), []);

  /** pointer x (px within the svg) -> fraction of the full domain */
  const toFrac = useCallback((px: number, [a, b]: [number, number]) => {
    const u = (px - plot.l) / (plot.w - plot.l - plot.r);
    return a + Math.max(0, Math.min(1, u)) * (b - a);
  }, [plot.l, plot.r, plot.w]);

  // native wheel listener (React's is passive, so it could not stop the page from scrolling)
  const bind = useCallback((el: SVGSVGElement | null, fracNow: [number, number]) => {
    if (!el) return () => {};
    const onWheel = (e: WheelEvent) => {
      const r = el.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * plot.w;
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        zoomAt(toFrac(px, fracNow), Math.exp(e.deltaY * 0.01));
      } else if (Math.abs(e.deltaX) > Math.abs(e.deltaY) && zoomed) {
        e.preventDefault();
        pan((e.deltaX / plot.w) * (fracNow[1] - fracNow[0]));
      }
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [pan, plot.w, toFrac, zoomAt, zoomed]);

  return { domain, frac, zoomed, zoomAt, pan, reset, toFrac, bind };
}

/** drag to pan, double-click to zoom in; returns pointer handlers and whether a drag is in progress */
export function useDragPan(svgRef: RefObject<SVGSVGElement | null>, z: ReturnType<typeof useZoom>, width: number) {
  const drag = useRef<{ x: number; f: [number, number] } | null>(null);
  const [dragging, setDragging] = useState(false);
  const px = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect();
    return ((e.clientX - r.left) / r.width) * width;
  };
  return {
    dragging,
    onPointerDown: (e: React.PointerEvent) => {
      if (!z.zoomed || e.button !== 0) return;
      drag.current = { x: px(e), f: z.frac };
      setDragging(true);
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
    },
    onPointerMoveDrag: (e: React.PointerEvent) => {
      if (!drag.current) return false;
      const dx = px(e) - drag.current.x;
      const span = drag.current.f[1] - drag.current.f[0];
      z.pan(-(dx / width) * span - (z.frac[0] - drag.current.f[0]));
      return true;
    },
    onPointerUp: () => { drag.current = null; setDragging(false); },
    onDoubleClick: (e: React.MouseEvent) => {
      const r = svgRef.current!.getBoundingClientRect();
      z.zoomAt(z.toFrac(((e.clientX - r.left) / r.width) * width, z.frac), 0.5);
    },
  };
}

export function ZoomControls({ z, labels, span }: {
  z: ReturnType<typeof useZoom>; labels: { in: string; out: string; reset: string }; span: string;
}) {
  const btn = "inline-flex h-8 w-8 items-center justify-center rounded-md border border-rule bg-sheet text-ink-2 transition-[color,transform] duration-150 ease-out hover:text-bank active:scale-[0.96] disabled:opacity-40";
  const mid = (z.frac[0] + z.frac[1]) / 2;
  return (
    <div className="flex items-center gap-1.5">
      <span className="num mr-1 text-[12.5px] text-ink-3">{span}</span>
      <button type="button" className={btn} onClick={() => z.zoomAt(mid, 0.5)} aria-label={labels.in} title={labels.in}><ZoomIn size={16} strokeWidth={1.75} /></button>
      <button type="button" className={btn} onClick={() => z.zoomAt(mid, 2)} disabled={!z.zoomed} aria-label={labels.out} title={labels.out}><ZoomOut size={16} strokeWidth={1.75} /></button>
      <button type="button" className={btn} onClick={z.reset} disabled={!z.zoomed} aria-label={labels.reset} title={labels.reset}><Maximize2 size={15} strokeWidth={1.75} /></button>
    </div>
  );
}

/** tick step for a time span: 2 h, 1 h, 30 min or 15 min */
export function tickStep(spanMs: number): number {
  const H = 3600_000;
  if (spanMs > 9 * H) return 2 * H;
  if (spanMs > 4.5 * H) return H;
  if (spanMs > 2 * H) return H / 2;
  return H / 4;
}

export function useBind(ref: RefObject<SVGSVGElement | null>, z: ReturnType<typeof useZoom>) {
  useEffect(() => z.bind(ref.current, z.frac), [ref, z]);
}

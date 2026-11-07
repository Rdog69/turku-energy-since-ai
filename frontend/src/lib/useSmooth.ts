import { useEffect, useRef, useState } from "react";

const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * A [min, max] range that glides to its target (critically damped, about 200 ms) instead of jumping, so scales,
 * windows and boxes move smoothly. Jumps further than `snap` (in units of the range) are applied at once.
 */
export function useSmoothRange(target: [number, number], tau = 70, snap = Infinity): [number, number] {
  const [cur, setCur] = useState<[number, number]>(target);
  const curRef = useRef(cur);
  const raf = useRef<number | null>(null);
  const [a, b] = target;

  useEffect(() => {
    const [c0, c1] = curRef.current;
    if (reduced() || Math.abs(a - c0) > snap || Math.abs(b - c1) > snap) {
      curRef.current = [a, b];
      setCur([a, b]);
      return;
    }
    let last = performance.now();
    const tick = (now: number) => {
      // rAF timestamps can precede the performance.now() taken when the effect ran: never step backwards
      const k = 1 - Math.exp(-Math.max(0, now - last) / tau);
      last = Math.max(last, now);
      const [x0, x1] = curRef.current;
      const n0 = x0 + (a - x0) * k, n1 = x1 + (b - x1) * k;
      const done = Math.abs(a - n0) <= Math.abs(b - a) * 1e-4 && Math.abs(b - n1) <= Math.abs(b - a) * 1e-4;
      curRef.current = done ? [a, b] : [n0, n1];
      setCur(curRef.current);
      raf.current = done ? null : requestAnimationFrame(tick);
    };
    if (raf.current !== null) cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(tick);
    return () => { if (raf.current !== null) cancelAnimationFrame(raf.current); raf.current = null; };
  }, [a, b, tau, snap]);

  return cur;
}

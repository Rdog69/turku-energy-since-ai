/**
 * The mark: a percent sign whose slash is a lightning bolt (a price, in probabilities). White, no background.
 * The wordmark: TASEHINTA in Michroma, every A drawn as an open chevron (an upside-down V).
 */
export function LogoMark({ size = 30, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-hidden>
      <circle cx="8.6" cy="8.6" r="4.3" fill="none" stroke="currentColor" strokeWidth="2.6" />
      <circle cx="23.4" cy="23.4" r="4.3" fill="none" stroke="currentColor" strokeWidth="2.6" />
      <path d="M24.6 1.6 L12.6 17.2 L18.2 17.2 L7.4 30.4 L20.2 14.6 L14.6 14.6 Z" fill="currentColor" />
    </svg>
  );
}

/** inline SVG source of the mark, for the favicon (blue on light tabs, white on dark ones) */
export const FAVICON_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><style>*{color:#0B3C6A}@media (prefers-color-scheme:dark){*{color:#fff}}</style>` +
  `<circle cx="8.6" cy="8.6" r="4.3" fill="none" stroke="currentColor" stroke-width="2.6"/>` +
  `<circle cx="23.4" cy="23.4" r="4.3" fill="none" stroke="currentColor" stroke-width="2.6"/>` +
  `<path d="M24.6 1.6 L12.6 17.2 L18.2 17.2 L7.4 30.4 L20.2 14.6 L14.6 14.6 Z" fill="currentColor"/></svg>`;

const Chevron = () => (
  <svg viewBox="0 0 100 100" aria-hidden className="inline-block h-[0.72em] w-[0.9em] align-baseline" style={{ marginInline: "0.02em" }}>
    <polyline points="5,100 50,5 95,100" fill="none" stroke="currentColor" strokeWidth="13" strokeLinejoin="miter" strokeMiterlimit="10" />
  </svg>
);

export function Wordmark({ text = "Tasehinta", className = "" }: { text?: string; className?: string }) {
  return (
    <span className={`inline-flex items-baseline whitespace-nowrap uppercase ${className}`} style={{ fontFamily: "Michroma, sans-serif", letterSpacing: "0.08em" }}
      aria-label={text} role="img">
      {text.toUpperCase().split("").map((c, k) => (c === "A" ? <Chevron key={k} /> : <span key={k} aria-hidden>{c}</span>))}
    </span>
  );
}

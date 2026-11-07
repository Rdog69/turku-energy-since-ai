/**
 * Tasehinta mark: a lightning bolt (electricity) on the brand-blue tile, with the two balancing directions as
 * dots: red top-left (up-regulation, price above spot) and teal bottom-right (down-regulation, price below).
 * The same drawing is the favicon (index.html).
 */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <rect width="32" height="32" rx="8" fill="#ffffff" fillOpacity="0.12" />
      <rect x="0.5" y="0.5" width="31" height="31" rx="7.5" fill="none" stroke="#ffffff" strokeOpacity="0.28" />
      <path d="M18.2 4.5 8.6 18h6.6l-2 9.5L23.4 14h-6.6z" fill="#ffffff" />
      <circle cx="8" cy="8" r="2.6" fill="#E0623F" />
      <circle cx="24" cy="24" r="2.6" fill="#18A39C" />
    </svg>
  );
}

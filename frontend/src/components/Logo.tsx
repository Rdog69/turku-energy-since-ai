/**
 * Tasehinta mark: a lightning bolt (electricity) between two dots, the balancing directions (up, down).
 * White on the blue rail; the favicon (index.html) is the same drawing.
 */
export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <path d="M18.2 4.5 8.6 18h6.6l-2 9.5L23.4 14h-6.6z" fill="#ffffff" />
      <circle cx="8" cy="8" r="2.6" fill="#ffffff" />
      <circle cx="24" cy="24" r="2.6" fill="#ffffff" />
    </svg>
  );
}

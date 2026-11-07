import * as Tooltip from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";
import { driverIcon } from "@/lib/icons";
import { driverLabel } from "@/lib/i18n";
import type { Lang } from "@/lib/time";

/** a hover card on any element (keyboard focus shows it too) */
export function Tip({ text, children, side = "top" }: { text: ReactNode; children: ReactNode; side?: "top" | "right" | "bottom" }) {
  return (
    <Tooltip.Root delayDuration={120}>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content side={side} sideOffset={6}
          className="z-50 max-w-[280px] rounded-md border border-rule bg-sheet px-3 py-2 text-[13.5px] leading-snug text-ink shadow-[0_6px_20px_-8px_rgba(20,34,51,0.35)]">
          {text}
          <Tooltip.Arrow className="fill-sheet" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/** "k in 10": ten dots, k filled */
export function ChanceDots({ k, tone }: { k: number; tone: "verm" | "teal" | "bank" }) {
  const fill = tone === "verm" ? "bg-verm" : tone === "teal" ? "bg-teal" : "bg-bank";
  return (
    <span className="inline-flex gap-1" aria-label={`${k} / 10`}>
      {Array.from({ length: 10 }, (_, j) => (
        <span key={j} className={`h-3 w-3 rounded-full ${j < k ? fill : "bg-rule"}`} />
      ))}
    </span>
  );
}

/** a driver as an icon chip */
export function DriverChip({ token, lang }: { token: string; lang: Lang }) {
  const { Icon, tag } = driverIcon(token);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-rule bg-sheet px-2.5 py-1 text-[12.5px] text-ink-2">
      <Icon size={14} strokeWidth={1.75} className="shrink-0 text-bank" />
      {tag && <span className="font-semibold text-ink">{tag}</span>}
      <span>{driverLabel(token, lang)}</span>
    </span>
  );
}

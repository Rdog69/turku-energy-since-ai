import * as Tooltip from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

/** Exact numbers live in hover cards (keyboard: focus shows them too), keeping the main screen quiet. */
export function HourTip({ text, children }: { text: string; children: ReactNode }) {
  return (
    <Tooltip.Root delayDuration={120}>
      <Tooltip.Trigger asChild>
        <button type="button" className="block w-full rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bank focus-visible:ring-offset-2">
          {children}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content side="top" sideOffset={6}
          className="z-50 max-w-[260px] rounded-md border border-rule bg-sheet px-3 py-2 text-[13.5px] leading-snug text-ink shadow-[0_6px_20px_-8px_rgba(20,34,51,0.35)]">
          {text}
          <Tooltip.Arrow className="fill-sheet" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

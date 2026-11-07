// One icon family (Lucide, 1.75 stroke) for drivers, alert kinds and views.
import {
  Activity, ArrowLeftRight, Atom, CalendarDays, CircleArrowUp, Clock, CloudFog, Euro, Flame, Gauge, Heater,
  Plug, RefreshCw, Scale, Split, Sun, Thermometer, TrendingDown, TrendingUp, MoveVertical, Waves, Wind, type LucideIcon,
} from "lucide-react";
import type { AlertKind } from "@/data/types";

export const ALERT_ICON: Record<AlertKind, LucideIcon> = {
  spike_high: TrendingUp,
  spike_low: TrendingDown,
  dir_up: CircleArrowUp,
  changed: RefreshCw,
  conflict: Split,
  review: MoveVertical,
};

/** icon for one of Frank's driver names, plus a country tag for neighbour weather */
export function driverIcon(token: string): { Icon: LucideIcon; tag?: string } {
  const country = token.match(/^om_(se|ee|no|dk)_/)?.[1]?.toUpperCase();
  if (token.includes("wind")) return { Icon: Wind, tag: country };
  if (token.includes("temp")) return { Icon: Thermometer };
  if (token.includes("solar")) return { Icon: Sun };
  if (token.includes("cons") || token.includes("residual_load")) return { Icon: Plug };
  if (token.includes("freq")) return { Icon: Activity };
  if (token.includes("hydro")) return { Icon: Waves };
  if (token.includes("nuclear")) return { Icon: Atom };
  if (token.includes("boiler")) return { Icon: Heater };
  if (token.includes("flow")) return { Icon: ArrowLeftRight };
  if (token.includes("model_spread")) return { Icon: CloudFog };
  if (token.includes("mfrr")) return { Icon: Gauge };
  if (token === "weekday") return { Icon: CalendarDays };
  if (token === "hour") return { Icon: Clock };
  if (token.includes("gap")) return { Icon: Scale };
  if (token.includes("spot")) return { Icon: Euro };
  return { Icon: Flame };
}

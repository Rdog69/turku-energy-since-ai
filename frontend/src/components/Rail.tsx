import { Factory, Info, LayoutDashboard, Lock, ShieldCheck, type LucideIcon } from "lucide-react";
import { PAYLOAD, PERIOD_IDS } from "@/lib/model";
import { Tip } from "./Bits";
import { Logo } from "./Logo";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/time";

// Simple and Trader were united into one Overview page (team feedback, 7 Nov); their components stay in the code.
export type View = "overview" | "production";
export const VIEWS: View[] = ["overview", "production"];
const VIEW_KEYS: Record<View, [string, string, LucideIcon]> = {
  overview: ["vOverview", "vOverviewHint", LayoutDashboard], production: ["vProd", "vProdHint", Factory],
};

export function Rail({ period, setPeriod, lang, view, setView }: {
  period: string; setPeriod: (p: string) => void; lang: Lang; setLang?: (l: Lang) => void; view: View; setView: (v: View) => void;
}) {
  const seg = (on: boolean) =>
    `w-full rounded-[4px] px-3 py-2 text-left text-[14px] font-semibold transition-colors duration-150 ${on ? "bg-white text-bank" : "text-bank-ink hover:bg-white/10"}`;
  return (
    <aside className="flex flex-col gap-8 bg-bank px-5 py-6 text-bank-ink lg:sticky lg:top-0 lg:h-screen lg:w-[244px] lg:shrink-0">
      <div className="flex flex-col items-center text-center">
        <p className="flex items-center gap-2 text-white" aria-label="Tasehinta"><Logo /><Wordmark /></p>
        <p className="mt-1.5 text-[14px] text-bank-ink2">{t(lang, "tagline")}</p>
      </div>

      <nav aria-label={t(lang, "view")} className="space-y-1.5">
        <p className="text-[13px] font-semibold text-bank-ink2">{t(lang, "view")}</p>
        {VIEWS.map((v) => {
          const [label, hint, Icon] = VIEW_KEYS[v];
          return (
            <Tip key={v} text={t(lang, hint)} side="right">
              <button type="button" aria-pressed={view === v} onClick={() => setView(v)} className={`${seg(view === v)} flex items-center gap-2.5`}>
                <Icon size={18} strokeWidth={1.75} className="shrink-0" />{t(lang, label)}
              </button>
            </Tip>
          );
        })}
      </nav>

      <nav aria-label={t(lang, "period")} className="space-y-1.5">
        <p className="text-[13px] font-semibold text-bank-ink2">{t(lang, "period")}</p>
        {PERIOD_IDS.map((id) => (
          <button key={id} type="button" aria-pressed={period === id} onClick={() => setPeriod(id)} className={seg(period === id)}>
            {PAYLOAD.periods[id].label[lang]}
          </button>
        ))}
      </nav>


      <ul className="mt-auto space-y-1">
        {([["infoModel", "modelText", Info], ["infoRules", "rules", ShieldCheck], ["infoLocal", "local", Lock]] as const).map(([label, text, Icon]) => (
          <li key={label}>
            <Tip text={t(lang, text)} side="right">
              <button type="button" className="flex w-full items-center gap-2.5 rounded-[4px] px-3 py-1.5 text-left text-[13.5px] text-bank-ink2 transition-colors duration-150 hover:bg-white/10 hover:text-white">
                <Icon size={16} strokeWidth={1.75} className="shrink-0" />{t(lang, label)}
              </button>
            </Tip>
          </li>
        ))}
      </ul>
    </aside>
  );
}

/** TASEHINTA in bold capitals; each A is an upside-down V (no crossbar), for a sharper, angular mark */
function Wordmark() {
  const A = <span className="inline-block rotate-180">V</span>;
  return (
    <span aria-hidden className="text-[23px] font-extrabold uppercase leading-none tracking-[0.06em]">
      T{A}SEHINT{A}
    </span>
  );
}

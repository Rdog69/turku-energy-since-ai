import { PAYLOAD, PERIOD_IDS } from "@/lib/model";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/time";

export type View = "simple" | "trader" | "production";
export const VIEWS: View[] = ["simple", "trader", "production"];
const VIEW_KEYS: Record<View, [string, string]> = {
  simple: ["vSimple", "vSimpleHint"], trader: ["vTrader", "vTraderHint"], production: ["vProd", "vProdHint"],
};

export function Rail({ period, setPeriod, lang, setLang, view, setView }: {
  period: string; setPeriod: (p: string) => void; lang: Lang; setLang: (l: Lang) => void; view: View; setView: (v: View) => void;
}) {
  const seg = (on: boolean) =>
    `w-full rounded-[4px] px-3 py-2 text-left text-[14px] font-semibold transition-colors duration-150 ${on ? "bg-white text-bank" : "text-bank-ink hover:bg-white/10"}`;
  return (
    <aside className="flex flex-col gap-8 bg-bank px-5 py-6 text-bank-ink lg:sticky lg:top-0 lg:h-screen lg:w-[244px] lg:shrink-0">
      <div>
        <p className="text-[26px] font-bold leading-none tracking-[-0.01em] text-white">Tasehinta</p>
        <p className="mt-1.5 text-[14px] text-bank-ink2">{t(lang, "tagline")}</p>
      </div>

      <nav aria-label={t(lang, "view")} className="space-y-1.5">
        <p className="text-[13px] font-semibold text-bank-ink2">{t(lang, "view")}</p>
        {VIEWS.map((v) => (
          <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)} className={seg(view === v)}>
            <span className="block">{t(lang, VIEW_KEYS[v][0])}</span>
            <span className={`block text-[12.5px] font-normal ${view === v ? "text-ink-2" : "text-bank-ink2"}`}>{t(lang, VIEW_KEYS[v][1])}</span>
          </button>
        ))}
      </nav>

      <nav aria-label={t(lang, "period")} className="space-y-1.5">
        <p className="text-[13px] font-semibold text-bank-ink2">{t(lang, "period")}</p>
        {PERIOD_IDS.map((id) => (
          <button key={id} type="button" aria-pressed={period === id} onClick={() => setPeriod(id)} className={seg(period === id)}>
            {PAYLOAD.periods[id].label[lang]}
          </button>
        ))}
      </nav>

      <div className="space-y-1.5">
        <p className="text-[13px] font-semibold text-bank-ink2">{t(lang, "language")}</p>
        <div className="grid grid-cols-2 gap-1 rounded-md bg-white/10 p-1">
          {(["en", "fi"] as Lang[]).map((l) => (
            <button key={l} type="button" aria-pressed={lang === l} onClick={() => setLang(l)}
              className={`rounded-[4px] py-1.5 text-[14px] font-semibold transition-colors duration-150 ${lang === l ? "bg-white text-bank" : "text-bank-ink hover:bg-white/10"}`}>
              {l === "en" ? "English" : "Suomi"}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4 text-[13.5px] leading-snug">
        <div>
          <p className="font-semibold text-white">{t(lang, "model")}</p>
          <p className="mt-1 text-bank-ink2">{t(lang, "modelText")}</p>
        </div>
        <p className="text-bank-ink2">{t(lang, "rules")}</p>
      </div>

      <p className="mt-auto text-[12px] leading-snug text-bank-ink2">{t(lang, "local")}</p>
    </aside>
  );
}

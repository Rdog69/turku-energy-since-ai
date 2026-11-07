import { useCallback, useEffect, useMemo, useState } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { ChevronDown } from "lucide-react";
import { Rail, VIEWS, type View } from "@/components/Rail";
import { SimpleView } from "@/components/SimpleView";
import { ProductionView } from "@/components/ProductionView";
import { TimeBar } from "@/components/TimeBar";
import { ChartLegend, FanChart } from "@/components/FanChart";
import { AlertList, alertKey } from "@/components/AlertList";
import { QuarterTable } from "@/components/QuarterTable";
import { Hindsight } from "@/components/Hindsight";
import type { Alert } from "@/data/types";
import { PAYLOAD, PERIOD_IDS, defaultHour, sortedAlerts } from "@/lib/model";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/time";

function readPref<T extends string>(k: string, ok: readonly T[], d: T): T {
  try {
    const v = localStorage.getItem(k) as T | null;
    return v && ok.includes(v) ? v : d;
  } catch {
    return d;
  }
}
function writePref(k: string, v: string) {
  try { localStorage.setItem(k, v); } catch { /* private mode */ }
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(() => readPref("tasehinta.lang", ["en", "fi"] as const, "en"));
  const [periodId, setPeriodId] = useState<string>(() => PERIOD_IDS[0]);
  const p = PAYLOAD.periods[periodId];
  const [i, setI] = useState(() => defaultHour(p));
  const [playing, setPlaying] = useState(false);
  const [focusKey, setFocusKey] = useState<string | null>(null);
  const [view, setViewState] = useState<View>(() => readPref("tasehinta.view", VIEWS, "simple"));
  const [details, setDetails] = useState(false);
  const setView = (v: View) => { setViewState(v); writePref("tasehinta.view", v); setFocusKey(null); };

  const setLang = (l: Lang) => { setLangState(l); writePref("tasehinta.lang", l); };
  const setPeriod = (id: string) => { setPeriodId(id); setI(defaultHour(PAYLOAD.periods[id])); setPlaying(false); setFocusKey(null); };

  useEffect(() => { document.documentElement.lang = lang; document.title = `Tasehinta: ${t(lang, "tagline")}`; }, [lang]);

  const alerts = useMemo(() => sortedAlerts(p, i), [p, i]);
  const focus: Alert | null = useMemo(() => alerts.find((a) => alertKey(a) === focusKey) ?? null, [alerts, focusKey]);

  const step = useCallback((d: number) => setI((v) => Math.max(0, Math.min(p.origins.length - 1, v + d))), [p]);

  // play: one forecast hour every 0.7 s
  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setI((v) => {
        if (v >= p.origins.length - 1) { setPlaying(false); return v; }
        return v + 1;
      });
    }, 700);
    return () => window.clearInterval(id);
  }, [playing, p]);

  // keyboard: arrows move an hour, shift+arrows a day, space plays
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("[role=slider], input, textarea, select")) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        setPlaying(false);
        step((e.key === "ArrowRight" ? 1 : -1) * (e.shiftKey ? 24 : 1));
      } else if (e.key === " " && !el.closest("button")) {
        e.preventDefault();
        setPlaying((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step]);

  return (
    <Tooltip.Provider delayDuration={120} skipDelayDuration={0}>
    <div className="min-h-screen bg-paper lg:flex">
      <Rail period={periodId} setPeriod={setPeriod} lang={lang} setLang={setLang} view={view} setView={setView} />
      <main className="min-w-0 flex-1 px-4 pb-16 pt-6 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-[1480px] space-y-8">
          <TimeBar p={p} i={i} setI={setI} lang={lang} playing={playing} setPlaying={setPlaying} />

          {view === "simple" && <SimpleView p={p} i={i} lang={lang} periodKey={periodId} />}
          {view === "production" && <ProductionView p={p} i={i} lang={lang} periodKey={periodId} />}
          {view === "trader" && (<>
          <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
            <section aria-labelledby="next-h" className="min-w-0">
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-3">
                <h1 id="next-h" className="text-[22px] font-bold text-ink">
                  {t(lang, "next10")} <span className="font-semibold text-ink-3">{t(lang, "chartTitle")}</span>
                </h1>
                <ChartLegend lang={lang} />
              </div>
              <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
                <FanChart p={p} i={i} lang={lang} focus={focus} periodKey={periodId} />
              </div>
            </section>
            <AlertList p={p} i={i} alerts={alerts} lang={lang} focus={focus} onFocus={(a) => setFocusKey(a ? alertKey(a) : null)} />
          </div>

          <div>
            <button type="button" onClick={() => setDetails(!details)} aria-expanded={details}
              className="rounded-md border border-rule bg-sheet px-4 py-2 text-[14px] font-semibold text-bank transition-transform duration-150 ease-out active:scale-[0.96]">
              <span className="inline-flex items-center gap-1.5">{details ? t(lang, "hideDetails") : t(lang, "details")}<ChevronDown size={16} strokeWidth={2} className={`transition-transform duration-150 ${details ? "rotate-180" : ""}`} /></span>
            </button>
          </div>
          {details && <QuarterTable p={p} i={i} lang={lang} focus={focus} />}
          {details && <Hindsight p={p} i={i} lang={lang} />}
          </>)}
        </div>
      </main>
    </div>
    </Tooltip.Provider>
  );
}

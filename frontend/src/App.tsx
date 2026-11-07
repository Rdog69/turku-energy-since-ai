import { useCallback, useEffect, useState } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { Rail, VIEWS, type View } from "@/components/Rail";
import { OverviewView } from "@/components/OverviewView";
import { ProductionView } from "@/components/ProductionView";
import { TimeBar } from "@/components/TimeBar";
import { PAYLOAD, PERIOD_IDS, defaultHour } from "@/lib/model";
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
  const [view, setViewState] = useState<View>(() => readPref("tasehinta.view", VIEWS, "overview"));
  const setView = (v: View) => { setViewState(v); writePref("tasehinta.view", v); };

  const setLang = (l: Lang) => { setLangState(l); writePref("tasehinta.lang", l); };
  const setPeriod = (id: string) => { setPeriodId(id); setI(defaultHour(PAYLOAD.periods[id])); setPlaying(false); };

  useEffect(() => { document.documentElement.lang = lang; document.title = `Tasehinta: ${t(lang, "tagline")}`; }, [lang]);

  const step = useCallback((d: number) => setI((v) => Math.max(0, Math.min(p.origins.length - 1, v + d))), [p]);

  // play: one forecast hour every 0.7 s (the Overview page runs its own smooth 15-minute glide)
  useEffect(() => {
    if (!playing || view === "overview") return;
    const id = window.setInterval(() => {
      setI((v) => {
        if (v >= p.origins.length - 1) { setPlaying(false); return v; }
        return v + 1;
      });
    }, 700);
    return () => window.clearInterval(id);
  }, [playing, p, view]);

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
      <main className="min-w-0 flex-1 px-4 pb-16 pt-5 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-[1480px] space-y-6">
          {view !== "overview" && <TimeBar p={p} i={i} setI={setI} lang={lang} playing={playing} setPlaying={setPlaying} />}

          {view === "overview" && <OverviewView p={p} i={i} setI={setI} playing={playing} setPlaying={setPlaying} lang={lang} />}
          {view === "production" && <ProductionView p={p} i={i} lang={lang} periodKey={periodId} />}
        </div>
      </main>
    </div>
    </Tooltip.Provider>
  );
}

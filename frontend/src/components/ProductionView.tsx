import { useMemo, useState } from "react";
import { ChevronDown, CircleArrowDown, CircleArrowUp, Flame, Heater, Minus, TriangleAlert } from "lucide-react";
import type { Period } from "@/data/types";
import { hourRuns, hourSummary, qMs } from "@/lib/model";
import { t } from "@/lib/i18n";
import { hhmm, type Lang } from "@/lib/time";
import { ChartLegend, FanChart } from "./FanChart";
import { HourTip } from "./HourTip";
import { QuarterTable } from "./QuarterTable";

/** For the production shift supervisor: when the grid needs more or less power, and where flexibility could pay. */
export function ProductionView({ p, i, lang, periodKey }: { p: Period; i: number; lang: Lang; periodKey: string }) {
  const [details, setDetails] = useState(false);
  const hs = useMemo(() => hourSummary(p, i), [p, i]);
  const o = p.origins[i];
  const at = (h: number) => hhmm(qMs(p, o + 4 * h), lang);
  const pctMax = (a: number, b: number, key: "pu" | "lo" | "hi") => Math.round(Math.max(...hs.slice(a, b + 1).map((x) => x[key])) * 100);

  const upRuns = hourRuns(hs, (x) => x.pu >= 0.6);
  const cheapRuns = hourRuns(hs, (x) => x.pd >= 0.7 && x.lo >= 0.5);
  const highRuns = hourRuns(hs, (x) => x.hi >= 0.4);
  const meanPd = hs.reduce((a, x) => a + x.pd, 0) / hs.length;
  const mode = upRuns.length ? "up" : meanPd >= 0.6 ? "down" : "mixed";
  const head = mode === "up" ? t(lang, "pUpShort", { a: at(upRuns[0][0]), b: at(upRuns[0][1] + 1) })
    : mode === "down" ? t(lang, "pDownShort") : t(lang, "pMixedShort");
  const HeadIcon = mode === "up" ? CircleArrowUp : mode === "down" ? CircleArrowDown : Minus;
  const headTone = mode === "up" ? "bg-verm-soft text-verm" : mode === "down" ? "bg-teal-soft text-teal" : "bg-accent text-ink-2";

  const opps = [
    ...highRuns.map(([a, b]) => ({ k: `h${a}`, Icon: TriangleAlert, tone: "bg-verm-soft text-verm", title: t(lang, "oppHighT"), detail: t(lang, "oppHighD"), when: `${at(a)}–${at(b + 1)}`, p: pctMax(a, b, "hi") })),
    ...upRuns.map(([a, b]) => ({ k: `u${a}`, Icon: Flame, tone: "bg-verm-soft text-verm", title: t(lang, "oppUpT"), detail: t(lang, "oppUpD"), when: `${at(a)}–${at(b + 1)}`, p: pctMax(a, b, "pu") })),
    ...cheapRuns.map(([a, b]) => ({ k: `c${a}`, Icon: Heater, tone: "bg-teal-soft text-teal", title: t(lang, "oppCheapT"), detail: t(lang, "oppCheapD"), when: `${at(a)}–${at(b + 1)}`, p: pctMax(a, b, "lo") })),
  ];

  const BAR = 132;
  return (
    <div className="space-y-10">
      <section aria-live="polite" className="flex items-center gap-5">
        <span className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-full ${headTone}`}><HeadIcon size={34} strokeWidth={2} /></span>
        <p className="num text-[30px] font-bold leading-tight text-ink">{head}</p>
      </section>

      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section aria-labelledby="p-bars">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="p-bars" className="text-[18px] font-bold text-ink">{t(lang, "pTitle")}</h2>
            <span className="flex gap-4 text-[13px] text-ink-2">
              <span className="inline-flex items-center gap-1.5"><CircleArrowUp size={15} strokeWidth={2} className="text-verm" />{t(lang, "pUpLbl")}</span>
              <span className="inline-flex items-center gap-1.5"><CircleArrowDown size={15} strokeWidth={2} className="text-teal" />{t(lang, "pDownLbl")}</span>
            </span>
          </div>
          <ol className="grid grid-cols-10 gap-1.5">
            {hs.map((x) => (
              <li key={x.h}>
                <HourTip text={`${at(x.h)}–${at(x.h + 1)}: ${t(lang, "up")} ${Math.round(x.pu * 100)} %, ${t(lang, "down")} ${Math.round(x.pd * 100)} %`}>
                  <span className="flex flex-col" style={{ height: BAR }}>
                    <span className="bg-verm/80" style={{ height: x.pu * BAR }} />
                    <span className="bg-rule" style={{ height: Math.max(0, 1 - x.pu - x.pd) * BAR }} />
                    <span className="bg-teal/80" style={{ height: x.pd * BAR }} />
                  </span>
                </HourTip>
                <span className="num mt-1 block text-center text-[12.5px] text-ink-3">{at(x.h)}</span>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="p-opp">
          <h2 id="p-opp" className="border-b border-rule pb-2 text-[18px] font-bold text-ink">{t(lang, "pOpp")}</h2>
          {opps.length === 0 ? (
            <p className="py-4 text-[15px] text-ink-2">{t(lang, "pNone")}</p>
          ) : (
            <ul className="divide-y divide-rule">
              {opps.map((x) => (
                <li key={x.k} className="flex items-start gap-3 py-3">
                  <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${x.tone}`} aria-hidden><x.Icon size={18} strokeWidth={2} /></span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="text-[15px] font-semibold text-ink">{x.title}</span>
                      <span className="num shrink-0 text-[13px] font-semibold text-ink-2">{x.when}</span>
                    </span>
                    <span className="mt-0.5 flex items-center justify-between gap-3 text-[13.5px] text-ink-2">
                      <span>{x.detail}</span><span className="num shrink-0">{x.p} %</span>
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section aria-label={t(lang, "sMedian")}>
        <div className="mb-2"><ChartLegend lang={lang} simple /></div>
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <FanChart p={p} i={i} lang={lang} focus={null} periodKey={periodKey} simple />
        </div>
      </section>

      <div>
        <button type="button" onClick={() => setDetails(!details)} aria-expanded={details}
          className="rounded-md border border-rule bg-sheet px-4 py-2 text-[14px] font-semibold text-bank transition-transform duration-150 ease-out active:scale-[0.96]">
          <span className="inline-flex items-center gap-1.5">{details ? t(lang, "hideDetails") : t(lang, "details")}<ChevronDown size={16} strokeWidth={2} className={`transition-transform duration-150 ${details ? "rotate-180" : ""}`} /></span>
        </button>
        {details && <div className="mt-6"><QuarterTable p={p} i={i} lang={lang} focus={null} /></div>}
      </div>
    </div>
  );
}

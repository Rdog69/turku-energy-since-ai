import { useMemo, useState } from "react";
import { ArrowUpDown, CalendarClock, CircleCheck, Minus, Scale, Target, TrendingDown, TrendingUp } from "lucide-react";
import type { Period } from "@/data/types";
import { hindsight, hourRuns, hourSummary, qMs, type HourSummary } from "@/lib/model";
import { t } from "@/lib/i18n";
import { hhmm, type Lang } from "@/lib/time";
import { ChartLegend, FanChart } from "./FanChart";
import { ChanceDots, ResToggle, Tip, type Res } from "./Bits";

/** For people outside the trade: a status badge, a traffic-light row, the expected price and its likely range. */
export function SimpleView({ p, i, lang, periodKey }: { p: Period; i: number; lang: Lang; periodKey: string }) {
  const [res, setRes] = useState<Res>("q");
  const size = res === "q" ? 1 : 4;
  const hs = useMemo(() => hourSummary(p, i, size), [p, i, size]);
  const track = useMemo(() => hindsight(p, i, 168), [p, i]);
  const o = p.origins[i];
  const at = (h: number) => hhmm(qMs(p, o + size * h), lang);

  // the headline stays hourly (robust); the row below can show every quarter-hour
  const hours = useMemo(() => hourSummary(p, i, 4), [p, i]);
  const hat = (h: number) => hhmm(qMs(p, o + 4 * h), lang);
  const pick = (lvl: HourSummary["level"]) => hourRuns(hours, (x) => x.level === lvl)[0];
  const run = pick("high") ?? pick("watch");
  const seg = run ? hours.slice(run[0], run[1] + 1) : [];
  const side = seg.some((x) => x.side === "high") ? "high" : "low";
  const k = run ? Math.max(1, Math.round(Math.max(...seg.map((x) => (side === "high" ? x.hi : x.lo))) * 10)) : 0;
  const tone = !run ? "bank" : side === "high" ? "verm" : "teal";
  const Big = !run ? CircleCheck : side === "high" ? TrendingUp : TrendingDown;
  const ring = { bank: "bg-bank/10 text-bank", verm: "bg-verm-soft text-verm", teal: "bg-teal-soft text-teal" }[tone];

  const maxMiss = Math.max(track.mae || 0, track.maeSpot || 0, 1);

  return (
    <div className="space-y-10">
      {/* status badge */}
      <section aria-live="polite" className="flex flex-wrap items-center gap-6">
        <span className={`flex h-20 w-20 shrink-0 items-center justify-center rounded-full ${ring}`}>
          <Big size={40} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <p className="text-[32px] font-bold leading-tight text-ink">
            {!run ? t(lang, "hCalm") : t(lang, side === "high" ? "hHigh" : "hLow")}
          </p>
          {run ? (
            <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-2 text-[18px]">
              <span className={`num font-semibold ${tone === "verm" ? "text-verm" : "text-teal"}`}>{hat(run[0])}–{hat(run[1] + 1)}</span>
              <span className="inline-flex items-center gap-2 text-ink-2"><ChanceDots k={k} tone={tone} />{t(lang, "chance", { k })}</span>
            </p>
          ) : (
            <p className="mt-1 text-[18px] text-ink-2">{t(lang, "hCalmSub")}</p>
          )}
        </div>
      </section>

      {/* traffic-light hours */}
      <section aria-labelledby="s-next">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <span className="flex items-center gap-3">
            <h2 id="s-next" className="text-[18px] font-bold text-ink">{t(lang, "sNext10")}</h2>
            <ResToggle res={res} setRes={setRes} lang={lang} t={t} />
          </span>
          <span className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-ink-2">
            <span className="inline-flex items-center gap-1.5"><TrendingUp size={15} strokeWidth={2} className="text-verm" />{t(lang, "hHigh")}</span>
            <span className="inline-flex items-center gap-1.5"><TrendingDown size={15} strokeWidth={2} className="text-teal" />{t(lang, "hLow")}</span>
            <span className="inline-flex items-center gap-1.5"><i className="h-3 w-3 rounded-[3px] bg-ink-2" />{t(lang, "sRisk")}</span>
            <span className="inline-flex items-center gap-1.5"><i className="h-3 w-3 rounded-[3px] border border-ink-3 bg-accent" />{t(lang, "sWatch")}</span>
            <span className="inline-flex items-center gap-1.5"><Minus size={15} strokeWidth={2} className="text-ink-3" />{t(lang, "sNormal")}</span>
          </span>
        </div>
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <ol className={res === "q" ? "grid min-w-[760px] grid-cols-[repeat(40,minmax(0,1fr))] gap-[3px]" : "grid grid-cols-5 gap-2 sm:grid-cols-10"}>
          {hs.map((x) => {
            const hiSide = x.side === "high";
            const cls = x.level === "normal" ? "border-rule bg-sheet text-ink-3"
              : hiSide ? (x.level === "high" ? "border-verm bg-verm text-white" : "border-verm bg-verm-soft text-verm")
                : (x.level === "high" ? "border-teal bg-teal text-white" : "border-teal bg-teal-soft text-teal");
            const Icon = x.level === "normal" ? Minus : hiSide ? TrendingUp : TrendingDown;
            const tip = x.level === "normal"
              ? `${at(x.h)}–${at(x.h + 1)}: ${t(lang, "sHourNormal", { v: Math.round(x.p50) })}`
              : `${at(x.h)}–${at(x.h + 1)}: ${t(lang, hiSide ? "sHourHigh" : "sHourLow", { p: Math.round((hiSide ? x.hi : x.lo) * 100) })}`;
            return (
              <li key={x.h}>
                <Tip text={tip}>
                  {res === "h" ? (
                  <button type="button" className={`flex h-[76px] w-full flex-col items-start justify-between rounded-md border px-2.5 py-2 transition-transform duration-150 ease-out active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bank focus-visible:ring-offset-2 ${cls}`}>
                    <span className="num text-[14px] font-semibold">{at(x.h)}</span>
                    <Icon size={22} strokeWidth={2} />
                  </button>
                  ) : (
                  <button type="button" aria-label={`${at(x.h)}–${at(x.h + 1)}`} className={`flex h-[64px] w-full flex-col items-center justify-end rounded-[3px] border pb-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bank focus-visible:ring-offset-1 ${cls}`}>
                    <Icon size={14} strokeWidth={2.25} />
                  </button>
                  )}
                </Tip>
                {res === "q" && <span className="num block h-4 whitespace-nowrap pt-0.5 text-[11px] text-ink-3">{x.h % 4 === 0 ? at(x.h) : ""}</span>}
              </li>
            );
          })}
        </ol>
        </div>
      </section>

      {/* the chart */}
      <section aria-label={t(lang, "sMedian")}>
        <div className="mb-2"><ChartLegend lang={lang} simple /></div>
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <FanChart p={p} i={i} lang={lang} focus={null} periodKey={periodKey} simple />
        </div>
      </section>

      <section className="grid gap-10 border-t border-rule pt-6 md:grid-cols-2">
        {/* glossary as chips; the definition sits in the hover card */}
        <div>
          <h2 className="mb-3 text-[18px] font-bold text-ink">{t(lang, "sGlossary")}</h2>
          <div className="flex flex-wrap gap-2">
            {([["gImb", Scale], ["gSpot", CalendarClock], ["gReg", ArrowUpDown]] as const).map(([key, Icon]) => (
              <Tip key={key} text={t(lang, `${key}Text`)}>
                <button type="button" className="inline-flex items-center gap-2 rounded-full border border-rule bg-sheet px-3.5 py-2 text-[14px] font-semibold text-ink transition-colors duration-150 hover:border-bank hover:text-bank focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bank">
                  <Icon size={16} strokeWidth={1.75} className="text-bank" />{t(lang, key)}
                </button>
              </Tip>
            ))}
          </div>
        </div>

        {/* track record as two bars */}
        {track.n > 0 && (
          <div>
            <h2 className="mb-3 inline-flex items-center gap-2 text-[18px] font-bold text-ink">
              <Target size={18} strokeWidth={2} className="text-bank" />{t(lang, "trackTitle")}
            </h2>
            {[[t(lang, "trackOurs"), track.mae, "bg-bank"], [t(lang, "trackSpot"), track.maeSpot, "bg-ink-3/45"]].map(([label, v, c]) => (
              <div key={label as string} className="mb-2.5 grid grid-cols-[150px_1fr] items-center gap-3 text-[14px]">
                <span className="text-ink-2">{label}</span>
                <span className="flex items-center gap-2">
                  <span className="min-w-0 flex-1"><span className={`block h-3.5 rounded-[3px] ${c}`} style={{ width: `${((v as number) / maxMiss) * 100}%` }} /></span>
                  <span className="num w-[84px] shrink-0 text-right font-semibold text-ink">{Math.round(v as number)} €/MWh</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

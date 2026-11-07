import { useMemo } from "react";
import type { Period } from "@/data/types";
import { hindsight, hourRuns, hourSummary, qMs, type HourSummary } from "@/lib/model";
import { t } from "@/lib/i18n";
import { hhmm, type Lang } from "@/lib/time";
import { ChartLegend, FanChart } from "./FanChart";
import { HourTip } from "./HourTip";

/** For people outside the trade: one sentence, a traffic-light row, the expected price and its likely range. */
export function SimpleView({ p, i, lang, periodKey }: { p: Period; i: number; lang: Lang; periodKey: string }) {
  const hs = useMemo(() => hourSummary(p, i), [p, i]);
  const track = useMemo(() => hindsight(p, i, 168), [p, i]);
  const o = p.origins[i];
  const at = (h: number) => hhmm(qMs(p, o + 4 * h), lang);

  // headline: the most serious stretch of hours, else calm
  const pick = (lvl: HourSummary["level"]) => hourRuns(hs, (x) => x.level === lvl)[0];
  const run = pick("high") ?? pick("watch");
  let head: string, sub: string | null;
  if (run) {
    const seg = hs.slice(run[0], run[1] + 1);
    const side = seg.some((x) => x.side === "high") ? "high" : "low";
    const pmax = Math.max(...seg.map((x) => (side === "high" ? x.hi : x.lo)));
    head = t(lang, side === "high" ? "sHigh" : "sLow", { a: at(run[0]), b: at(run[1] + 1) });
    sub = t(lang, "sChance", { p: Math.max(1, Math.round(pmax * 10)) });
  } else {
    head = t(lang, "sCalm");
    const pd = hs.reduce((a, x) => a + x.pd, 0) / hs.length;
    sub = pd >= 0.55 ? t(lang, "sCalmSub") : null;
  }

  return (
    <div className="space-y-10">
      <section aria-live="polite" className="max-w-[68ch]">
        <p className="text-[30px] font-bold leading-tight text-ink">{head}</p>
        {sub && <p className="mt-2 text-[18px] text-ink-2">{sub}</p>}
      </section>

      <section aria-labelledby="s-next">
        <h2 id="s-next" className="mb-3 text-[18px] font-bold text-ink">{t(lang, "sNext10")}</h2>
        <ol className="grid grid-cols-5 gap-2 sm:grid-cols-10">
          {hs.map((x) => {
            const tone = x.level === "normal"
              ? "border-rule bg-sheet text-ink-2"
              : x.side === "high"
                ? x.level === "high" ? "border-verm bg-verm text-white" : "border-verm bg-verm-soft text-verm"
                : x.level === "high" ? "border-teal bg-teal text-white" : "border-teal bg-teal-soft text-teal";
            const word = t(lang, x.level === "high" ? "sRisk" : x.level === "watch" ? "sWatch" : "sNormal");
            const tip = x.level === "normal"
              ? t(lang, "sHourNormal", { v: Math.round(x.p50) })
              : t(lang, x.side === "high" ? "sHourHigh" : "sHourLow", { p: Math.round((x.side === "high" ? x.hi : x.lo) * 100) });
            return (
              <li key={x.h}>
                <HourTip text={tip}>
                  <span className={`flex h-[72px] w-full flex-col justify-between rounded-md border px-2.5 py-2 text-left ${tone}`}>
                    <span className="num text-[14px] font-semibold">{at(x.h)}</span>
                    <span className="text-[13px] font-semibold">{word}</span>
                  </span>
                </HourTip>
              </li>
            );
          })}
        </ol>
      </section>

      <section aria-label={t(lang, "sMedian")}>
        <div className="mb-2"><ChartLegend lang={lang} simple /></div>
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <FanChart p={p} i={i} lang={lang} focus={null} periodKey={periodKey} simple />
        </div>
      </section>

      <section className="grid gap-8 border-t border-rule pt-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          <h2 className="mb-3 text-[18px] font-bold text-ink">{t(lang, "sGlossary")}</h2>
          <dl className="space-y-3 text-[15px]">
            {(["gImb", "gSpot", "gReg"] as const).map((k) => (
              <div key={k}>
                <dt className="font-semibold text-ink">{t(lang, k)}</dt>
                <dd className="text-ink-2">{t(lang, `${k}Text`)}</dd>
              </div>
            ))}
          </dl>
        </div>
        {track.n > 0 && (
          <p className="self-start text-[17px] leading-snug text-ink">
            {t(lang, "sTrack", { v: Math.round(track.mae), s: Math.round(track.maeSpot) })}
          </p>
        )}
      </section>
    </div>
  );
}

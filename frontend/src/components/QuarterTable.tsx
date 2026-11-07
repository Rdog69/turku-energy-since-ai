import type { Alert, Period } from "@/data/payload";
import { STEPS, driverTokens, forecastAt, known, qMs, reviewMin } from "@/lib/model";
import { driverLabel, t } from "@/lib/i18n";
import { hhmm, type Lang } from "@/lib/time";

const f0 = (v: number | null) => (v === null ? "–" : Math.round(v).toString());
const pc = (v: number) => `${Math.round(v * 100)}`;

export function QuarterTable({ p, i, lang, focus }: { p: Period; i: number; lang: Lang; focus: Alert | null }) {
  const F = forecastAt(p, i);
  const o = p.origins[i];
  const T = reviewMin(p, i);
  return (
    <section aria-labelledby="qt-h">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-2">
        <h2 id="qt-h" className="text-[18px] font-bold text-ink">{t(lang, "table")}</h2>
        <span className="text-[13px] text-ink-3">{t(lang, "tableHint")}</span>
      </div>
      <div className="max-h-[420px] overflow-auto">
        <table className="w-full border-collapse text-[13.5px]">
          <thead className="sticky top-0 z-[1] bg-paper text-left text-[12.5px] text-ink-2">
            <tr className="border-b border-rule">
              <th scope="col" className="py-2 pr-3 font-semibold">{t(lang, "q")}</th>
              <th scope="col" className="py-2 pr-3 text-right font-semibold">{t(lang, "colSpot")}</th>
              <th scope="col" className="py-2 pr-3 text-right font-semibold text-bank">{t(lang, "colMedian")}</th>
              <th scope="col" className="py-2 pr-3 text-right font-semibold">{t(lang, "colBand")}</th>
              <th scope="col" className="py-2 pr-3 text-right font-semibold">{t(lang, "colUp")} %</th>
              <th scope="col" className="py-2 pr-3 text-right font-semibold">{t(lang, "colDown")} %</th>
              <th scope="col" className="py-2 pr-3 text-right font-semibold text-verm">{t(lang, "colHigh")} %</th>
              <th scope="col" className="py-2 pr-3 text-right font-semibold text-teal">{t(lang, "colLow")} %</th>
              <th scope="col" className="py-2 font-semibold">{t(lang, "colDrivers")}</th>
            </tr>
          </thead>
          <tbody className="num">
            {Array.from({ length: STEPS }, (_, s) => {
              const gi = o + s;
              const inFocus = focus !== null && s >= focus.a && s <= focus.b;
              const hourStart = s % 4 === 0;
              return (
                <tr key={s} className={`${inFocus ? "bg-accent/70" : ""} ${hourStart ? "border-t border-rule" : ""}`}>
                  <td className={`py-1 pr-3 ${hourStart ? "font-semibold text-ink" : "text-ink-2"}`}>{hhmm(qMs(p, gi), lang)}</td>
                  <td className="py-1 pr-3 text-right text-ink-2">{f0(known(p.spot, p.spot_fu, gi, T))}</td>
                  <td className="py-1 pr-3 text-right font-semibold text-bank">{f0(F.p50[s])}</td>
                  <td className="py-1 pr-3 text-right text-ink-2">{f0(F.p10[s])} – {f0(F.p90[s])}</td>
                  <td className="py-1 pr-3 text-right text-ink-2">{pc(F.pu[s])}</td>
                  <td className="py-1 pr-3 text-right text-ink-2">{pc(F.pd[s])}</td>
                  <td className={`py-1 pr-3 text-right ${F.hi[s] >= 0.4 ? "font-bold text-verm" : "text-ink-2"}`}>{pc(F.hi[s])}</td>
                  <td className={`py-1 pr-3 text-right ${F.lo[s] >= 0.5 ? "font-bold text-teal" : "text-ink-2"}`}>{pc(F.lo[s])}</td>
                  <td className="py-1 font-sans text-[12.5px] text-ink-2">{driverTokens(p, i, s).slice(0, 3).map((d) => driverLabel(d, lang)).join(", ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

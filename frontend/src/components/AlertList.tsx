import { useState } from "react";
import type { Alert, Period } from "@/data/types";
import { qMs, reviewMs, windowDrivers } from "@/lib/model";
import { t } from "@/lib/i18n";
import { ALERT_ICON } from "@/lib/icons";
import { DriverChip } from "./Bits";
import { Q_MS, hhmm, type Lang } from "@/lib/time";

const MARK: Record<Alert["kind"], string> = {
  spike_high: "bg-verm-soft text-verm",
  spike_low: "bg-teal-soft text-teal",
  dir_up: "bg-verm-soft text-verm",
  changed: "bg-accent text-ochre",
  conflict: "bg-accent text-ochre",
  review: "bg-accent text-ink-2",
};

export function alertKey(a: Alert) {
  return `${a.kind}:${a.a}:${a.b}`;
}

export function AlertList({ p, i, alerts, lang, focus, onFocus }: {
  p: Period; i: number; alerts: Alert[]; lang: Lang; focus: Alert | null; onFocus: (a: Alert | null) => void;
}) {
  const [showRoutine, setShowRoutine] = useState(false);
  const o = p.origins[i];
  // the organisers' guidance: significant events in colour, routine items quiet and collapsed
  const major = alerts.filter((a) => a.level === "high" || a.kind === "spike_high" || a.kind === "spike_low");
  const routine = alerts.filter((a) => !major.includes(a));
  const prev = hhmm(reviewMs(p, i) - 3600_000, lang);
  const win = (a: Alert) => ({ a: hhmm(qMs(p, o + a.a), lang), b: hhmm(qMs(p, o + a.b) + Q_MS, lang) });

  return (
    <section aria-labelledby="worth-h" className="flex h-full flex-col">
      <div className="flex items-baseline justify-between border-b border-rule pb-2">
        <h2 id="worth-h" className="text-[18px] font-bold text-ink">{t(lang, "worth")}</h2>
        <span className="num text-[13px] text-ink-3">
          {alerts.length === 1 ? t(lang, "worthOne") : t(lang, "worthCount", { n: alerts.length })}
        </span>
      </div>

      {alerts.length === 0 ? (
        <div className="py-6">
          <p className="text-[15px] font-semibold text-ink">{t(lang, "quiet")}</p>
          <p className="mt-1 text-[14px] text-ink-2">{t(lang, "quietSub")}</p>
        </div>
      ) : (
        <>
        {major.length === 0 && (
          <div className="py-4">
            <p className="text-[15px] font-semibold text-ink">{t(lang, "quiet")}</p>
          </div>
        )}
        <ul className="divide-y divide-rule">
          {[...major, ...(showRoutine ? routine : [])].map((a) => {
            const k = alertKey(a);
            const open = focus !== null && alertKey(focus) === k;
            const dim = focus !== null && !open;
            const w = win(a);
            const pv = Math.round(a.value * 100);
            const v = Math.round(Math.abs(a.value));
            const title = t(lang, `t.${a.kind}`, { ...w, v: a.kind === "changed" ? `${a.value > 0 ? "+" : "−"}${v}` : v });
            const detail = t(lang, `d.${a.kind}`, { p: pv, v, prev });
            const rise = a.rise !== null && a.rise !== undefined && Math.abs(a.rise) >= 0.05
              ? t(lang, a.rise > 0 ? "rise" : "fall", { d: Math.round(Math.abs(a.rise) * 100), prev }) : null;
            const drivers = windowDrivers(p, i, a.a, a.b);
            return (
              <li key={k} className={`transition-opacity duration-150 ease-out ${dim ? "opacity-50" : "opacity-100"}`}>
                <button type="button" aria-expanded={open} onClick={() => onFocus(open ? null : a)}
                  className="group flex w-full items-start gap-3 py-3 text-left">
                  {(() => { const Icon = ALERT_ICON[a.kind]; return (
                    <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${major.includes(a) ? MARK[a.kind] : "bg-accent text-ink-3"}`} aria-hidden>
                      <Icon size={17} strokeWidth={2} />
                    </span>); })()}
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="num text-[15px] font-semibold leading-snug text-ink group-hover:text-bank">{title}</span>
                      <span className={`shrink-0 text-[12px] font-semibold ${a.level === "high" ? "text-verm" : "text-ink-3"}`}>
                        {t(lang, `level_${a.level}`)}
                      </span>
                    </span>
                    {(a.kind === "spike_high" || a.kind === "spike_low" || a.kind === "dir_up") && (
                      <span className={`num mt-0.5 block text-[13px] ${a.kind === "spike_low" ? "text-teal" : "text-verm"}`}>
                        {pv} %.{rise && <span className="text-ink-2"> {rise}</span>}
                      </span>
                    )}
                    {open && (
                      <span className="mt-2 block space-y-2 text-[14px] text-ink-2">
                        <span className="block">{detail}</span>
                        {drivers.length > 0 && (
                          <span className="flex flex-wrap gap-1.5">{drivers.map((d) => <DriverChip key={d} token={d} lang={lang} />)}</span>
                        )}
                        <span className="block rounded-[4px] bg-paper px-2.5 py-2 font-semibold text-ink">
                          {t(lang, `s.${a.kind}`, w)}
                        </span>
                      </span>
                    )}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
        {routine.length > 0 && (
          <button type="button" onClick={() => setShowRoutine(!showRoutine)} aria-expanded={showRoutine}
            className="mt-1 border-t border-rule pt-3 text-left text-[14px] font-semibold text-ink-3 hover:text-ink-2">
            {showRoutine ? t(lang, "hideDetails") : routine.length === 1 ? t(lang, "moreWatchOne") : t(lang, "moreWatch", { n: routine.length })}
          </button>
        )}
        </>
      )}
    </section>
  );
}

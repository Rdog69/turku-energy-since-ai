import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ChevronDown, CircleArrowDown, CircleArrowUp, CircleCheck, TrendingDown, TrendingUp, X } from "lucide-react";
import type { Alert, Period } from "@/data/types";
import { STEPS, driverTokens, forecastAt, hourRuns, hourSummary, known, qMs, reviewMin, reviewMs, sortedAlerts, windowDrivers } from "@/lib/model";
import { driverLabel, t } from "@/lib/i18n";
import { ALERT_ICON, driverIcon } from "@/lib/icons";
import { Q_MS, hhmm, type Lang } from "@/lib/time";
import { ChanceDots } from "./Bits";
import { BACK, H, TimeChart, TimeLegend } from "./TimeChart";
import { PeriodStrip, TimeBar } from "./TimeBar";
import { alertKey } from "./AlertList";
import { QuarterTable } from "./QuarterTable";
import { Hindsight } from "./Hindsight";

/**
 * One page for everyone (Simple and Trader united): a glance first, detail on demand.
 * Order: worth-checking chips (open a side panel), the headline, the wide chart, the 15-minute
 * risk and balancing rows (click a quarter for its detail), the key factors, then the full tables.
 */
export function OverviewView({ p, i, setI, playing, setPlaying, lang }: {
  p: Period; i: number; setI: Dispatch<SetStateAction<number>>; playing: boolean; setPlaying: (v: boolean) => void; lang: Lang;
}) {
  const [panel, setPanel] = useState<{ kind: "alert"; a: Alert } | { kind: "quarter"; s: number } | { kind: "all" } | null>(null);
  const [zones, setZones] = useState(false);
  // the graph window: "now" sits at BACK of the width. Scrolling, dragging and playback move "now" through time;
  // it rests on 15-minute steps past the forecast hour (the newest forecast is still that hour's).
  const Q = 15 * 60_000;
  const [span, setSpan] = useState(16 * H);
  const [offset, setOffset] = useState(0);            // 0 .. 45 min past forecast hour i
  const iRef = useRef(i); iRef.current = i;
  const offRef = useRef(offset);
  const n = p.origins.length;
  const shift = useCallback((ms: number) => {
    let off = offRef.current + ms, ni = iRef.current;
    while (off >= H) { if (ni >= n - 1) { off = 3 * Q; break; } ni++; off -= H; }
    while (off < 0) { if (ni <= 0) { off = 0; break; } ni--; off += H; }
    if (ni === n - 1) off = Math.min(off, 3 * Q);
    offRef.current = off;
    if (ni !== iRef.current) { iRef.current = ni; setI(ni); }
    setOffset(off);
  }, [n, setI, Q]);
  const pan = useCallback((ms: number) => { setPlaying(false); shift(ms); }, [shift, setPlaying]);
  const panEnd = useCallback(() => shift(Math.round(offRef.current / Q) * Q - offRef.current), [shift, Q]);
  const jump = useCallback((v: number) => { offRef.current = 0; setOffset(0); setI(v); }, [setI]);
  useEffect(() => { offRef.current = 0; setOffset(0); }, [p]);

  // playback: a smooth glide, 15 minutes every 0.6 s (one forecast hour in 2.4 s); pausing rests on a quarter-hour
  useEffect(() => {
    if (!playing) return;
    let raf = 0, last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(64, now - last); last = now;
      if (iRef.current >= n - 1 && offRef.current >= 3 * Q) { setPlaying(false); return; }
      shift(dt * (Q / 600));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); shift(Math.round(offRef.current / Q) * Q - offRef.current); };
  }, [playing, n, shift, setPlaying, Q]);

  const center = reviewMs(p, i) + offset;
  const view: [number, number] = [center - BACK * span, center + (1 - BACK) * span];
  const manipulated = span !== 16 * H || offset !== 0;
  const [details, setDetails] = useState(false);
  const alerts = useMemo(() => sortedAlerts(p, i), [p, i]);
  const major = alerts.filter((a) => a.level === "high" || a.kind === "spike_high" || a.kind === "spike_low");
  const focus = panel?.kind === "alert" ? panel.a : null;
  const o = p.origins[i];
  const win = (a: number, b: number) => ({ a: hhmm(qMs(p, o + a), lang), b: hhmm(qMs(p, o + b) + Q_MS, lang) });

  return (
    <div className="space-y-5">
      <Headline p={p} i={i} lang={lang} />

      <WorthChips lang={lang} alerts={alerts} major={major} win={win}
        onOpen={(a) => setPanel({ kind: "alert", a })} onAll={() => setPanel({ kind: "all" })} />

      <section aria-label={t(lang, "chartTitle")} className="rounded-xl border border-rule bg-sheet/50 px-4 pb-3 pt-4 sm:px-5">
        <TimeBar p={p} i={i} setI={jump} lang={lang} playing={playing} setPlaying={setPlaying} offset={offset} compact />
        <div className="mb-1 mt-4 flex flex-wrap items-center justify-between gap-3 pr-[150px]">
          <TimeLegend lang={lang} />
          <button type="button" onClick={() => setZones(!zones)} aria-pressed={zones}
            className={`rounded-md border px-3 py-1 text-[13px] font-semibold transition-colors duration-150 ${zones ? "border-bank bg-bank text-white" : "border-rule bg-sheet text-bank"}`}>
            {t(lang, "tcZones")}
          </button>
        </div>
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <TimeChart p={p} i={i} win={view} lang={lang} focus={focus} zones={zones} span={span}
            onPan={pan} onPanEnd={panEnd} onZoom={(f) => setSpan((v) => Math.max(2 * H, Math.min(96 * H, v * f)))}
            onResetZoom={() => { setSpan(16 * H); offRef.current = 0; setOffset(0); }} onQuarter={(s) => setPanel({ kind: "quarter", s })}
            nowOffset={offset} manipulated={manipulated} />
        </div>
        {/* where the graph sits in the whole period: a half-transparent window on the period strip */}
        <PeriodStrip p={p} i={i} win={view} onJump={(v) => { setPlaying(false); jump(v); }} lang={lang} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <BalanceSummary p={p} i={i} lang={lang} />
          <span className="text-[12.5px] text-ink-3">{t(lang, "tcHint")}</span>
        </div>
      </section>

      <KeyFactors p={p} i={i} lang={lang} />

      <div>
        <button type="button" onClick={() => setDetails(!details)} aria-expanded={details}
          className="rounded-md border border-rule bg-sheet px-4 py-2 text-[14px] font-semibold text-bank transition-transform duration-150 ease-out active:scale-[0.96]">
          <span className="inline-flex items-center gap-1.5">{details ? t(lang, "hideDetails") : t(lang, "details")}<ChevronDown size={16} strokeWidth={2} className={`transition-transform duration-150 ${details ? "rotate-180" : ""}`} /></span>
        </button>
        {details && <div className="mt-6 space-y-10"><QuarterTable p={p} i={i} lang={lang} focus={focus} /><Hindsight p={p} i={i} lang={lang} /></div>}
      </div>

      <Dialog.Root open={panel !== null} onOpenChange={(v) => { if (!v) setPanel(null); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/15" />
          <Dialog.Content aria-describedby={undefined}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[440px] flex-col overflow-y-auto border-l border-rule bg-sheet px-6 pb-8 pt-6 shadow-[-12px_0_32px_-16px_rgba(20,34,51,0.35)] focus:outline-none">
            <Dialog.Close aria-label={t(lang, "oClose")} className="absolute right-4 top-4 rounded-md p-1.5 text-ink-3 hover:bg-paper hover:text-ink">
              <X size={18} strokeWidth={2} />
            </Dialog.Close>
            {panel?.kind === "alert" && <AlertPanel p={p} i={i} lang={lang} a={panel.a} win={win} />}
            {panel?.kind === "quarter" && <QuarterPanel p={p} i={i} lang={lang} s={panel.s} />}
            {panel?.kind === "all" && (
              <>
                <Dialog.Title className="pr-8 text-[20px] font-bold text-ink">{t(lang, "worth")}</Dialog.Title>
                <ul className="mt-4 divide-y divide-rule">
                  {alerts.map((a) => (
                    <li key={alertKey(a)}>
                      <AlertRow a={a} lang={lang} win={win} major={major.includes(a)} onClick={() => setPanel({ kind: "alert", a })} />
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

const MARK: Record<Alert["kind"], string> = {
  spike_high: "bg-verm-soft text-verm", spike_low: "bg-teal-soft text-teal", dir_up: "bg-verm-soft text-verm",
  changed: "bg-accent text-ochre", conflict: "bg-accent text-ochre", review: "bg-accent text-ink-2",
};

function alertTitle(a: Alert, lang: Lang, w: { a: string; b: string }) {
  const v = Math.round(Math.abs(a.value));
  return t(lang, `t.${a.kind}`, { ...w, v: a.kind === "changed" ? `${a.value > 0 ? "+" : "−"}${v}` : v });
}

/** the significant items as chips right under the timeline; routine ones collapse into "+n more" */
function WorthChips({ lang, alerts, major, win, onOpen, onAll }: {
  lang: Lang; alerts: Alert[]; major: Alert[]; win: (a: number, b: number) => { a: string; b: string };
  onOpen: (a: Alert) => void; onAll: () => void;
}) {
  const shown = major.slice(0, 4);
  const rest = alerts.length - shown.length;
  return (
    <section aria-labelledby="o-worth" className="flex flex-wrap items-center gap-2">
      <h2 id="o-worth" className="mr-1 text-[15px] font-bold text-ink">{t(lang, "worth")}</h2>
      {alerts.length === 0 && <span className="text-[14px] text-ink-2">{t(lang, "quiet")}</span>}
      {shown.map((a) => {
        const Icon = ALERT_ICON[a.kind];
        return (
          <button key={alertKey(a)} type="button" onClick={() => onOpen(a)}
            className="inline-flex items-center gap-2 rounded-full border border-rule bg-sheet py-1 pl-1 pr-3.5 text-[13.5px] font-semibold text-ink transition-colors duration-150 hover:border-bank hover:text-bank">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full ${MARK[a.kind]}`} aria-hidden><Icon size={15} strokeWidth={2} /></span>
            <span className="num">{alertTitle(a, lang, win(a.a, a.b))}</span>
            {a.level === "high" && <span className="text-[12px] text-verm">{t(lang, "level_high")}</span>}
          </button>
        );
      })}
      {rest > 0 && (
        <button type="button" onClick={onAll}
          className="rounded-full border border-dashed border-rule px-3.5 py-1.5 text-[13.5px] font-semibold text-ink-3 hover:border-ink-3 hover:text-ink-2">
          {shown.length === 0 ? t(lang, "oAllItems", { n: rest }) : t(lang, "oMore", { n: rest })}
        </button>
      )}
    </section>
  );
}

function AlertRow({ a, lang, win, major, onClick }: { a: Alert; lang: Lang; win: (a: number, b: number) => { a: string; b: string }; major: boolean; onClick: () => void }) {
  const Icon = ALERT_ICON[a.kind];
  return (
    <button type="button" onClick={onClick} className="group flex w-full items-center gap-3 py-3 text-left">
      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${major ? MARK[a.kind] : "bg-accent text-ink-3"}`} aria-hidden><Icon size={16} strokeWidth={2} /></span>
      <span className="num min-w-0 flex-1 text-[15px] font-semibold text-ink group-hover:text-bank">{alertTitle(a, lang, win(a.a, a.b))}</span>
      <span className={`shrink-0 text-[12px] font-semibold ${a.level === "high" ? "text-verm" : "text-ink-3"}`}>{t(lang, `level_${a.level}`)}</span>
    </button>
  );
}

function AlertPanel({ p, i, lang, a, win }: { p: Period; i: number; lang: Lang; a: Alert; win: (a: number, b: number) => { a: string; b: string } }) {
  const w = win(a.a, a.b);
  const prev = hhmm(qMs(p, p.origins[i]) - 3600_000, lang);
  const pv = Math.round(a.value * 100);
  const v = Math.round(Math.abs(a.value));
  const Icon = ALERT_ICON[a.kind];
  const ranked = windowDrivers(p, i, a.a, a.b, 4);
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 pr-8">
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${MARK[a.kind]}`} aria-hidden><Icon size={20} strokeWidth={2} /></span>
        <Dialog.Title className="num text-[19px] font-bold leading-snug text-ink">{alertTitle(a, lang, w)}</Dialog.Title>
      </div>
      <p className="text-[15px] text-ink-2">{t(lang, `d.${a.kind}`, { p: pv, v, prev })}</p>
      {a.rise !== null && a.rise !== undefined && Math.abs(a.rise) >= 0.05 && (
        <p className="text-[14px] text-ink-2">{t(lang, a.rise > 0 ? "rise" : "fall", { d: Math.round(Math.abs(a.rise) * 100), prev })}</p>
      )}
      {ranked.length > 0 && (
        <div>
          <h3 className="mb-2 text-[14px] font-bold text-ink">{t(lang, "oDrivers")}</h3>
          <FactorList tokens={ranked} lang={lang} />
        </div>
      )}
      <p className="rounded-md bg-paper px-3 py-2.5 text-[15px] font-semibold text-ink">{t(lang, `s.${a.kind}`, w)}</p>
    </div>
  );
}

/** detail for one quarter-hour: price, range, direction, risks and its drivers in order of strength */
function QuarterPanel({ p, i, lang, s }: { p: Period; i: number; lang: Lang; s: number }) {
  const F = forecastAt(p, i);
  const o = p.origins[i];
  const T = reviewMin(p, i);
  const spot = known(p.spot, p.spot_fu, o + s, T);
  const pct = (v: number) => `${Math.round(v * 100)} %`;
  const eur = (v: number) => `${Math.round(v)} €/MWh`;
  const rows: [string, string, string?][] = [
    [t(lang, "sMedian"), eur(F.p50[s]), "text-ink font-bold"],
    [t(lang, "sBand"), `${Math.round(F.p10[s])} – ${Math.round(F.p90[s])} €/MWh`],
    [t(lang, "sSpot"), spot === null ? "–" : eur(spot)],
  ];
  return (
    <div className="space-y-6">
      <Dialog.Title className="num pr-8 text-[20px] font-bold text-ink">
        {t(lang, "oQuarter", { a: hhmm(qMs(p, o + s), lang), b: hhmm(qMs(p, o + s + 1), lang) })}
      </Dialog.Title>
      <dl className="space-y-1.5 text-[15px]">
        {rows.map(([k, v, c]) => (
          <div key={k} className="flex justify-between gap-4"><dt className="text-ink-2">{k}</dt><dd className={`num ${c ?? "text-ink"}`}>{v}</dd></div>
        ))}
      </dl>
      <div>
        <h3 className="mb-2 text-[14px] font-bold text-ink">{t(lang, "oBal")}</h3>
        <div className="flex h-4 overflow-hidden rounded-[4px]">
          <span className="bg-verm/80" style={{ width: `${F.pu[s] * 100}%` }} />
          <span className="bg-rule" style={{ width: `${F.pn[s] * 100}%` }} />
          <span className="bg-teal/80" style={{ width: `${F.pd[s] * 100}%` }} />
        </div>
        <div className="num mt-1.5 flex justify-between text-[13.5px]">
          <span className="text-verm">{t(lang, "up")} {pct(F.pu[s])}</span>
          <span className="text-teal">{t(lang, "down")} {pct(F.pd[s])}</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-md bg-verm-soft px-3 py-2.5"><p className="text-[13px] text-verm">{t(lang, "highRisk")}</p><p className="num text-[20px] font-bold text-verm">{pct(F.hi[s])}</p></div>
        <div className="rounded-md bg-teal-soft px-3 py-2.5"><p className="text-[13px] text-teal">{t(lang, "lowRisk")}</p><p className="num text-[20px] font-bold text-teal">{pct(F.lo[s])}</p></div>
      </div>
      <div>
        <h3 className="mb-2 text-[14px] font-bold text-ink">{t(lang, "oDrivers")}</h3>
        <FactorList tokens={driverTokens(p, i, s)} lang={lang} />
      </div>
      <p className="num text-[13px] text-ink-3">{t(lang, "oModels", { a: Math.round(F.frP50[s]), b: Math.round(F.ouP50[s]) })}</p>
    </div>
  );
}

/** factors in order of strength: the first stands out, the rest are quieter */
function FactorList({ tokens, lang }: { tokens: string[]; lang: Lang }) {
  return (
    <ol className="space-y-1.5">
      {tokens.map((d, k) => {
        const { Icon, tag } = driverIcon(d);
        const key = k === 0;
        return (
          <li key={d} className={`flex items-center gap-2.5 rounded-md px-3 py-2 ${key ? "bg-bank text-white" : "bg-paper text-ink-3"}`}>
            <Icon size={key ? 18 : 15} strokeWidth={key ? 2 : 1.75} className="shrink-0" />
            {tag && <span className="font-semibold">{tag}</span>}
            <span className={key ? "text-[15px] font-semibold" : "text-[13.5px]"}>{driverLabel(d, lang)}</span>
            <span className={`ml-auto text-[11.5px] ${key ? "text-white/75" : "text-ink-3"}`}>{t(lang, key ? "oKey" : "oMinor")}</span>
          </li>
        );
      })}
    </ol>
  );
}

/** the glance: one sentence about the next 10 hours (kept from the Simple view) */
function Headline({ p, i, lang }: { p: Period; i: number; lang: Lang }) {
  const hours = useMemo(() => hourSummary(p, i, 4), [p, i]);
  const o = p.origins[i];
  const hat = (h: number) => hhmm(qMs(p, o + 4 * h), lang);
  const pick = (lvl: "high" | "watch") => hourRuns(hours, (x) => x.level === lvl)[0];
  const run = pick("high") ?? pick("watch");
  const seg = run ? hours.slice(run[0], run[1] + 1) : [];
  const side = seg.some((x) => x.side === "high") ? "high" : "low";
  const k = run ? Math.max(1, Math.round(Math.max(...seg.map((x) => (side === "high" ? x.hi : x.lo))) * 10)) : 0;
  const tone = !run ? "bank" : side === "high" ? "verm" : "teal";
  const Big = !run ? CircleCheck : side === "high" ? TrendingUp : TrendingDown;
  const ring = { bank: "bg-bank/10 text-bank", verm: "bg-verm-soft text-verm", teal: "bg-teal-soft text-teal" }[tone];
  return (
    <section aria-live="polite" className="flex flex-wrap items-center gap-4">
      <span className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full ${ring}`}><Big size={30} strokeWidth={2} /></span>
      <div className="min-w-0">
        <p className="text-[26px] font-bold leading-tight text-ink">{!run ? t(lang, "hCalm") : t(lang, side === "high" ? "hHigh" : "hLow")}</p>
        {run ? (
          <p className="mt-0.5 flex flex-wrap items-center gap-x-4 gap-y-2 text-[16px]">
            <span className={`num font-semibold ${tone === "verm" ? "text-verm" : "text-teal"}`}>{hat(run[0])}–{hat(run[1] + 1)}</span>
            <span className="inline-flex items-center gap-2 text-ink-2"><ChanceDots k={k} tone={tone} />{t(lang, "chance", { k })}</span>
          </p>
        ) : (
          <p className="mt-0.5 text-[16px] text-ink-2">{t(lang, "hCalmSub")}</p>
        )}
      </div>
    </section>
  );
}

/** one sentence on the balancing direction over the next 10 hours */
function BalanceSummary({ p, i, lang }: { p: Period; i: number; lang: Lang }) {
  const F = useMemo(() => forecastAt(p, i), [p, i]);
  const meanUp = F.pu.reduce((a, v) => a + v, 0) / STEPS;
  const meanDn = F.pd.reduce((a, v) => a + v, 0) / STEPS;
  const sum = meanUp >= 0.5 ? "oBalSumUp" : meanDn >= 0.6 ? "oBalSumDown" : "oBalSumMixed";
  const Icon = meanUp >= 0.5 ? CircleArrowUp : CircleArrowDown;
  return (
    <p className="inline-flex items-center gap-2 text-[14.5px] font-semibold text-ink">
      <Icon size={18} strokeWidth={2} className={meanUp >= 0.5 ? "text-verm" : "text-teal"} />
      {t(lang, sum, { up: Math.round(meanUp * 100), down: Math.round(meanDn * 100) })}
    </p>
  );
}

/** the few factors that move the next 10 hours most; strongest stand out, weaker ones in grey */
function KeyFactors({ p, i, lang }: { p: Period; i: number; lang: Lang }) {
  const scored = useMemo(() => {
    const count = new Map<string, number>();
    for (let s = 0; s < STEPS; s++) driverTokens(p, i, s).forEach((d, r) => count.set(d, (count.get(d) ?? 0) + (3 - Math.min(r, 2))));
    const all = [...count.entries()].sort((a, b) => b[1] - a[1]);
    return all.slice(0, 5);
  }, [p, i]);
  if (scored.length === 0) return null;
  const top = scored[0][1];
  return (
    <section aria-labelledby="o-factors">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="o-factors" className="text-[18px] font-bold text-ink">{t(lang, "oDrivers")}</h2>
        <span className="text-[13px] text-ink-3">{t(lang, "oDriversHint")}</span>
      </div>
      <ul className="flex flex-wrap items-center gap-2">
        {scored.map(([d, sc]) => {
          const key = sc >= 0.5 * top;
          const { Icon, tag } = driverIcon(d);
          return (
            <li key={d} className={`inline-flex items-center gap-2 rounded-full ${key ? "bg-bank px-4 py-2 text-[15px] font-semibold text-white" : "border border-rule bg-paper px-3 py-1.5 text-[13px] text-ink-3"}`}>
              <Icon size={key ? 17 : 14} strokeWidth={key ? 2 : 1.75} className="shrink-0" />
              {tag && <span className="font-semibold">{tag}</span>}
              {driverLabel(d, lang)}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

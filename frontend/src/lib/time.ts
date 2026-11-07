// All times are shown in Finnish time (Europe/Helsinki); 25 Oct 2026 repeats 03:00-04:00 when daylight saving ends.
export type Lang = "en" | "fi";

const TZ = "Europe/Helsinki";
const fmtCache = new Map<string, Intl.DateTimeFormat>();

function fmt(lang: Lang, opts: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = lang + JSON.stringify(opts);
  let f = fmtCache.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat(lang === "fi" ? "fi-FI" : "en-GB", { timeZone: TZ, ...opts });
    fmtCache.set(key, f);
  }
  return f;
}

export const hhmm = (ms: number, lang: Lang) => fmt(lang, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(ms).replace(".", ":");
export const dayLong = (ms: number, lang: Lang) => fmt(lang, { weekday: "long", day: "numeric", month: "long" }).format(ms);
export const dayShort = (ms: number, lang: Lang) => fmt(lang, { weekday: "short", day: "numeric", month: "numeric" }).format(ms);
export const dateShort = (ms: number, lang: Lang) => fmt(lang, { day: "numeric", month: "short" }).format(ms);
export const hourOf = (ms: number) => Number(fmt("en", { hour: "2-digit", hourCycle: "h23" }).format(ms));

export const Q_MS = 15 * 60 * 1000;

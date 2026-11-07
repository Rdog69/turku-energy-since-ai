import type React from "react";
import type { Lang } from "@/lib/time";

/** US flag, simplified for 18 px (stripes and canton; stars would be invisible at this size) */
function FlagUS() {
  return (
    <svg width="18" height="12" viewBox="0 0 19 13" aria-hidden className="shrink-0 rounded-[2px] shadow-[0_0_0_1px_rgba(20,34,51,0.12)]">
      <rect width="19" height="13" fill="#B22234" />
      {[1, 3, 5, 7, 9, 11].map((y) => <rect key={y} y={y} width="19" height="1" fill="#fff" />)}
      <rect width="7.6" height="7" fill="#3C3B6E" />
    </svg>
  );
}

/** Finnish flag: blue Nordic cross on white */
function FlagFI() {
  return (
    <svg width="18" height="12" viewBox="0 0 18 11" aria-hidden className="shrink-0 rounded-[2px] shadow-[0_0_0_1px_rgba(20,34,51,0.12)]">
      <rect width="18" height="11" fill="#fff" />
      <rect x="5" width="3" height="11" fill="#002F6C" />
      <rect y="4" width="18" height="3" fill="#002F6C" />
    </svg>
  );
}

/** Language switch, top right of the page */
export function LangToggle({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  const opts: [Lang, string, () => React.ReactElement, string][] = [["en", "EN", FlagUS, "English"], ["fi", "FI", FlagFI, "Suomi"]];
  return (
    <div role="radiogroup" aria-label="Language / Kieli" className="inline-flex rounded-full border border-rule bg-sheet p-0.5 shadow-[0_1px_2px_rgba(20,34,51,0.06)]">
      {opts.map(([l, code, Flag, name]) => (
        <button key={l} type="button" role="radio" aria-checked={lang === l} title={name} onClick={() => setLang(l)}
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12.5px] font-semibold transition-colors duration-150 ${lang === l ? "bg-bank text-white" : "text-ink-2 hover:text-ink"}`}>
          <Flag />{code}
        </button>
      ))}
    </div>
  );
}

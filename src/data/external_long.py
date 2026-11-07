"""Abdo's master external Fingrid data (external_data/fingrid/*.csv.gz) in the package's long format.

The files already carry `first_usable_origin_utc` (fu). This loader does not trust them blindly:
it recomputes fu from the documented delay rules in `src/data/external/fingrid.py` (the DS tables
RT / PACKAGE / EXTRA) and keeps the **later** of the file's fu and the rule's fu, so a rule that
was too early in a file can never leak. At the time of writing the files agree with the rules on
every row (`fu_audit()` reports the number of rows that would be pushed later, currently 0 for
the default groups).

Groups and files (period "main" = 25 May - 2 Nov 2026, i.e. training + test window):

    "fingrid_rt"      rt_<period>.csv.gz       3-min real-time data averaged per quarter-hour:
                                               fu = ceil_hour(quarter_end + 30 min)
    "fingrid_extra"   extra_<period>.csv.gz    75, 176, 242, 243, 251, 268 (see DELAY_RULES)
    "fingrid_package" package_history.csv.gz   17 package series from Mar 2025 (period "history")

Series ids are the ones in the files (`fg<dataset id>_<name>`), e.g. `fg198_surplus_deficit_rt`.

Duplicates with `src/data/fingrid.py` (Frank's `fingrid_rt.parquet`): datasets 181, 188, 177, 193
(series fg_wind_rt, fg_nuclear_rt, fg_freq_rt, fg_cons_rt) exist in both. Frank's ids are kept so
existing features stay identical; the master copies are dropped (`FRANK_DUPLICATES`).
Differences found when comparing the overlap: identical fu everywhere; values identical except
5 frequency quarters (max |diff| 0.0064 Hz) and 1 consumption quarter (3.6 MW), because Frank
requires >= 3 of the 5 samples per quarter and the master files average whatever samples exist.

Pre-June history (the `last_autumn` period, Sep-Nov 2025, and the `history` period, package
series Mar 2025 - May 2026) is NOT loaded by default. The organisers allowed pre-June data on
7 Nov (QUESTIONS.md Q1), but no model reads these tables: the submitted v6_hf trains on Abdo's
separate package-format history (src.data.load.load_history). Pass `period="last_autumn"` /
`"history"` explicitly to load them.
"""
from __future__ import annotations

import pandas as pd

from src.config import REPO_ROOT
from src.data.external.fingrid import EXTRA, PACKAGE, RT, TZ
from src.data.load import LONG_COLUMNS

EXT_DIR = REPO_ROOT / "external_data" / "fingrid"

GROUPS = ("fingrid_rt", "fingrid_extra", "fingrid_package")
DEFAULT_GROUPS = ("fingrid_rt", "fingrid_extra")
DEFAULT_PERIOD = "main"
# group -> {period: file}. Periods other than "main" need an explicit argument.
FILES = {
    "fingrid_rt": {"main": "rt_main.csv.gz", "last_autumn": "rt_last_autumn.csv.gz"},
    "fingrid_extra": {"main": "extra_main.csv.gz", "last_autumn": "extra_last_autumn.csv.gz"},
    "fingrid_package": {"history": "package_history.csv.gz"},
}
PERIODS = ("main", "last_autumn", "history")

RT_DELAY = pd.Timedelta(minutes=30)
QUARTER = pd.Timedelta(minutes=15)

# Master datasets that Frank's loader (src/data/fingrid.py) already provides under other ids.
FRANK_DUPLICATES = {181: "fg_wind_rt", 188: "fg_nuclear_rt", 177: "fg_freq_rt", 193: "fg_cons_rt"}

# series_id -> DS (kind rt3 | period | daily, delay_min, publish_local), straight from the fetcher.
DELAY_RULES = {f"fg{d.id}_{d.name}": d for d in RT + PACKAGE + EXTRA}
# Series that are plans / forecasts made before the delivery time, so fu may precede the timestamp.
PLAN_SERIES = {sid for sid, d in DELAY_RULES.items() if d.kind == "daily"}

# Known data-quality problems of the master files (see the T2 report); informational only.
QUALITY_NOTES = {
    "fg209_power_system_state_rt": "constant 1 over the whole period (no information)",
    "fg243_mfrr_up_bids_sum": "constant 0 over the whole period (no information)",
    "fg251_mfrr_last_down_bid_price": "only 284 quarters (14-18 Oct), all 0; unusable",
    "fg268_wind_capacity": "piecewise constant (8 distinct values); a normaliser, not a signal",
}


def rule_first_usable(series_id: str, ts: pd.Series) -> pd.Series:
    """First usable time implied by the documented rule, for quarter-start timestamps `ts` (UTC)."""
    ds = DELAY_RULES[series_id]
    ts = pd.to_datetime(ts, utc=True)
    if ds.kind == "rt3":
        fu = ts + QUARTER + RT_DELAY
    elif ds.kind == "period":
        fu = ts + QUARTER + pd.Timedelta(minutes=ds.delay_min)
    elif ds.kind == "daily":
        # published at publish_local (Helsinki clock) on the local day before delivery
        day = ts.dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
        hh, mm = map(int, ds.publish_local.split(":"))
        pub = (day - pd.Timedelta(days=1) + pd.Timedelta(hours=hh, minutes=mm)).dt.tz_localize(TZ)
        fu = pub.dt.tz_convert("UTC")
    else:
        raise ValueError(f"unknown rule kind {ds.kind!r} for {series_id}")
    return fu.dt.ceil("h")


def _read(path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"dataset_id": str})
    for col in ("timestamp_utc", "first_usable_origin_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df[LONG_COLUMNS]


def _conservative_fu(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """fu := max(file fu, documented rule); returns the frame and rows pushed later per series."""
    df = df.copy()
    pushed = {}
    for sid, idx in df.groupby("series_id").groups.items():
        if sid not in DELAY_RULES:
            raise ValueError(f"no documented availability rule for external series {sid!r}")
        rule = rule_first_usable(sid, df.loc[idx, "timestamp_utc"])
        file_fu = df.loc[idx, "first_usable_origin_utc"]
        later = rule > file_fu
        pushed[sid] = int(later.sum())
        df.loc[idx, "first_usable_origin_utc"] = file_fu.where(~later, rule)
    return df, pushed


def _periods(period) -> tuple[str, ...]:
    periods = (period,) if isinstance(period, str) else tuple(period)
    bad = set(periods) - set(PERIODS)
    if bad:
        raise ValueError(f"unknown period(s) {sorted(bad)}; choose from {PERIODS}")
    return periods


def load_external_long(groups=DEFAULT_GROUPS, period="main", drop_frank_duplicates=True,
                       report: dict | None = None) -> pd.DataFrame:
    """Master external Fingrid series as a long table (LONG_COLUMNS, UTC), or an empty frame.

    groups: any of "fingrid_rt", "fingrid_extra", "fingrid_package".
    period: "main" (default; 25 May - 2 Nov 2026) is the only period loaded by default.
        "last_autumn" (Sep-Nov 2025) and "history" (package series Mar 2025 - May 2026, group
        "fingrid_package" only) are loaded only when passed explicitly (no model uses them). A tuple
        such as ("main", "last_autumn") loads both.
    drop_frank_duplicates: drop datasets 181/188/177/193 (Frank's fg_*_rt series are the
        canonical copies).
    report: optional dict, filled with {series_id: rows whose fu was pushed later than the file's}.

    first_usable_origin_utc is max(file value, documented rule), so every row obeys
    `first_usable_origin_utc <= origin` through SeriesIndex / available_at like the package rows.
    """
    for g in ([groups] if isinstance(groups, str) else groups):
        if g not in GROUPS:
            raise ValueError(f"unknown group {g!r}; choose from {GROUPS}")
    parts = []
    for g in ([groups] if isinstance(groups, str) else groups):
        for p in _periods(period):
            name = FILES[g].get(p)
            if name is None or not (EXT_DIR / name).exists():
                continue
            parts.append(_read(EXT_DIR / name))
    if not parts:
        return pd.DataFrame(columns=LONG_COLUMNS)
    df = pd.concat(parts, ignore_index=True)
    if drop_frank_duplicates:
        df = df.loc[~df["dataset_id"].astype(int).isin(FRANK_DUPLICATES)]
    # exact repeats (e.g. the DST fall-back hour in package_history) -> keep the last occurrence
    df = df.drop_duplicates(["series_id", "timestamp_utc"], keep="last")
    df, pushed = _conservative_fu(df)
    if report is not None:
        report.update(pushed)
    return df.sort_values(["series_id", "timestamp_utc"]).reset_index(drop=True)[LONG_COLUMNS]


def fu_audit(groups=GROUPS, period=PERIODS) -> dict[str, int]:
    """Rows per series whose file fu is EARLIER than the documented rule (should be empty/0).

    Reads the pre-June periods too; a diagnostic only, nothing is returned as data.
    """
    out: dict[str, int] = {}
    load_external_long(groups, period, report=out)
    return {k: v for k, v in out.items() if v}


def coverage(long: pd.DataFrame, windows: dict[str, tuple[str, str]], series_ids=None) -> pd.DataFrame:
    """Share of quarter-hours without a row, per series and window (start inclusive, end exclusive)."""
    rows = []
    for sid, g in long.groupby("series_id"):
        if series_ids is not None and sid not in series_ids:
            continue
        have = pd.DatetimeIndex(g["timestamp_utc"])
        row = {"series_id": sid}
        for name, (a, b) in windows.items():
            full = pd.date_range(a, b, freq="15min", tz="UTC", inclusive="left")
            row[f"missing_{name}"] = 1.0 - full.isin(have).mean()
        rows.append(row)
    return pd.DataFrame(rows)

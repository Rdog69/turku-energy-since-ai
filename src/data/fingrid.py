"""Fingrid Open Data real-time series (3-min), aggregated to quarter-hours.

These aren't in the starter package. We give them the **same availability rule the organisers use
for measured Fingrid data** (availability.csv: consumption/production and flows, 30 min after the
end of the period):

    first_usable_origin_utc = ceil_to_hour(quarter_end + 30 min)

Fingrid publishes these every 1-3 minutes, so 30 min is conservative. The result is appended to
the package's long table as extra series, so the same availability code and leakage tests apply.

    python -m src.data.fingrid --start 2026-05-29 --end 2026-11-02

Needs FINGRID_API_KEY in .env (developer-data.fingrid.fi, Open Data API). Data: Fingrid Open Data,
CC BY 4.0. Raw pages are cached in external_data/fingrid/raw/ (git-ignored).
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from src.config import REPO_ROOT

API = "https://data.fingrid.fi/api/datasets/{id}/data"
OUT_DIR = REPO_ROOT / "external_data" / "fingrid"
PUBLICATION_DELAY = pd.Timedelta(minutes=30)

DATASETS = {
    181: ("fg_wind_rt", "MW"),         # wind power production, real-time
    188: ("fg_nuclear_rt", "MW"),      # nuclear power production, real-time
    177: ("fg_freq_rt", "Hz"),         # grid frequency, real-time
    193: ("fg_cons_rt", "MW"),         # consumption in Finland, real-time
}


def api_key() -> str:
    env = {}
    path = REPO_ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    import os
    key = os.environ.get("FINGRID_API_KEY") or env.get("FINGRID_API_KEY")
    if not key:
        raise RuntimeError("FINGRID_API_KEY missing (add it to .env)")
    return key


def _get(url: str, key: str) -> dict:
    req = urllib.request.Request(url, headers={"x-api-key": key, "User-Agent": "sinceai-imbalance-forecast"})
    for attempt in range(8):
        try:
            return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = float(e.headers.get("Retry-After", 2)) + 1.5 * attempt
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"giving up on {url}")


def fetch_dataset(ds: int, start: str, end: str, key: str, pause: float = 2.0) -> pd.DataFrame:
    raw_dir = OUT_DIR / "raw" / str(ds)
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows, page, last_page = [], 1, 1
    while page <= last_page:
        cache = raw_dir / f"{start}_{end}_p{page}.json"
        if cache.exists():
            body = json.loads(cache.read_text(encoding="utf-8"))
        else:
            q = {"startTime": f"{start}T00:00:00Z", "endTime": f"{end}T00:00:00Z", "format": "json",
                 "pageSize": 20000, "page": page, "sortBy": "startTime", "sortOrder": "asc"}
            body = _get(API.format(id=ds) + "?" + urllib.parse.urlencode(q), key)
            cache.write_text(json.dumps(body), encoding="utf-8")
            time.sleep(pause)
        rows.extend(body.get("data", []))
        pag = body.get("pagination") or {}
        if page == 1:
            # only the first page reports the total; later pages omit nextPage
            last_page = int(pag.get("lastPage") or 1)
            total = pag.get("total")
        page += 1
    df = pd.DataFrame(rows).drop_duplicates(["startTime"])
    print(f"  dataset {ds}: {len(df)} raw rows of {total}, {last_page} page(s)")
    return df


def to_quarters(df: pd.DataFrame, series_id: str, unit: str, ds: int) -> pd.DataFrame:
    """3-min rows -> quarter-hour means, in the package's long format."""
    t = pd.to_datetime(df["startTime"], utc=True)
    q = t.dt.floor("15min")
    g = pd.DataFrame({"q": q, "value": pd.to_numeric(df["value"], errors="coerce")}).groupby("q")
    agg = g["value"].agg(["mean", "count"]).reset_index()
    agg = agg.loc[agg["count"] >= 3]   # need most of the quarter (5 samples of 3 min)
    out = pd.DataFrame({
        "series_id": series_id, "source": "fingrid_api", "dataset_id": str(ds),
        "timestamp_utc": agg["q"], "value": agg["mean"], "unit": unit,
    })
    out["first_usable_origin_utc"] = (out["timestamp_utc"] + pd.Timedelta(minutes=15)
                                      + PUBLICATION_DELAY).dt.ceil("h")
    return out


def download(start: str, end: str) -> Path:
    key = api_key()
    parts = []
    for ds, (sid, unit) in DATASETS.items():
        parts.append(to_quarters(fetch_dataset(ds, start, end, key), sid, unit, ds))
    long = pd.concat(parts, ignore_index=True)
    out = OUT_DIR / "fingrid_rt.parquet"
    long.to_parquet(out, index=False)
    print(f"wrote {out.relative_to(REPO_ROOT)}: {len(long)} quarter rows "
          + ", ".join(f"{s}={n}" for s, n in long.groupby('series_id').size().items()))
    return out


def load_long_extra() -> pd.DataFrame | None:
    path = OUT_DIR / "fingrid_rt.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    for col in ("timestamp_utc", "first_usable_origin_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-05-29")
    ap.add_argument("--end", default="2026-11-03")
    args = ap.parse_args(argv)
    download(args.start, args.end)


if __name__ == "__main__":
    main()

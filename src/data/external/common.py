"""Shared helpers for external-data fetchers.

Every fetcher writes rows with a `first_usable_origin_utc` column, computed from a
documented, conservative publication delay and rounded UP to the next full hour,
exactly like the starter package. Use the same `available_at()` filter on them.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "external_data"
CACHE = OUT / "_cache"          # raw responses, git-ignored; makes every fetch resumable

# Periods we fetch (UTC dates, end exclusive)
PERIODS = {
    # last autumn: the closest seasonal analogue of the test period (5 Oct - 1 Nov 2026)
    "last_autumn": ("2025-09-01", "2025-12-01"),
    # training + test window of the package, plus one week before for lags
    "main": ("2026-05-25", "2026-11-03"),
}

# Wind-power clusters (approximate coordinates of the big farm areas) + one load point.
# Finnish wind capacity is concentrated on the west coast (Ostrobothnia) and in the north-west.
POINTS = {
    "kristiinankaupunki": (62.27, 21.38),
    "vaasa": (63.10, 21.60),
    "kokkola": (63.84, 23.13),
    "lestijarvi": (63.53, 24.67),     # large inland farm
    "kalajoki": (64.26, 23.95),
    "raahe_pyhajoki": (64.62, 24.35),
    "ii_simo": (65.45, 25.05),
    "helsinki": (60.17, 24.94),       # temperature for consumption
}


def ceil_hour(ts: pd.Series) -> pd.Series:
    """Round UP to the next full hour (an exact full hour stays)."""
    return pd.to_datetime(ts, utc=True).dt.ceil("h")


def load_env() -> dict[str, str]:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("FINGRID", "ENTSOE"))})
    return env


class Http:
    """GET with a minimum interval between calls, retries on 429/5xx, and an on-disk cache."""

    def __init__(self, name: str, min_interval_s: float, headers: dict | None = None, timeout: int = 120):
        self.name, self.min_interval, self.headers, self.timeout = name, min_interval_s, headers or {}, timeout
        self._last = 0.0
        (CACHE / name).mkdir(parents=True, exist_ok=True)

    def get(self, url: str, params: dict | None = None, cache_key: str | None = None,
            retries: int = 6) -> bytes | None:
        path = CACHE / self.name / cache_key if cache_key else None
        if path and path.exists():
            return path.read_bytes()
        full = url + ("?" + urllib.parse.urlencode(params, safe=":,") if params else "")
        delay = 5.0
        for attempt in range(1, retries + 1):
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                req = urllib.request.Request(full, headers={"User-Agent": "since-ai-hackathon-team", **self.headers})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = r.read()
                if path:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(body)
                return body
            except urllib.error.HTTPError as e:
                body = e.read()[:300]
                if e.code == 400:            # e.g. "model run not available": not retryable
                    print(f"  [{self.name}] 400 {body!r}")
                    return None
                if e.code in (429,) or e.code >= 500:
                    print(f"  [{self.name}] HTTP {e.code}, retry {attempt} in {delay:.0f}s")
                    time.sleep(delay); delay = min(delay * 2, 300); continue
                raise RuntimeError(f"{self.name} HTTP {e.code}: {body!r}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                print(f"  [{self.name}] {e}, retry {attempt} in {delay:.0f}s")
                time.sleep(delay); delay = min(delay * 2, 300)
        raise RuntimeError(f"{self.name}: giving up on {full}")


def write(df: pd.DataFrame, source: str, name: str) -> Path:
    out = OUT / source
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.csv.gz"
    df.to_csv(p, index=False, date_format="%Y-%m-%dT%H:%M:%SZ", compression="gzip")
    print(f"wrote {p.relative_to(ROOT)}: {len(df):,} rows")
    return p


def json_loads(b: bytes):
    return json.loads(b.decode("utf-8"))

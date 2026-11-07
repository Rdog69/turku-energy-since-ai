"""Write an extended copy of the starter package (Mar 2025 - Nov 2026) for pipelines that read the package
directly (Frank's: set TE_PACKAGE_DIR to it and DATA_START to 2025-03-05). History rows come from
external_data/history/pkg_history.csv.gz (built by build_history.py) and only precede each series' first package
quarter, so there are no duplicate (series_id, timestamp_utc) rows. Spot history = Elering (Nord Pool): team-only.

    .venv/bin/python -m experiments.lab.build_package_ext
"""
from __future__ import annotations

import shutil

import pandas as pd

from .data import EXT, PKG

OUT = EXT / "history/package_ext"


def main():
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    inp = pd.read_parquet(PKG / "data/inputs.parquet")
    spot = pd.read_csv(PKG / "data/spot_nordpool.csv")
    h = pd.read_csv(EXT / "history/pkg_history.csv.gz", dtype={"dataset_id": str})
    for df in (inp, spot, h):                   # same types as the package parquet: UTC datetimes, strings
        for c in ("timestamp_utc", "first_usable_origin_utc"):
            df[c] = pd.to_datetime(df[c], utc=True).astype("datetime64[ns, UTC]")
    h["dataset_id"] = h["dataset_id"].fillna("").astype(str)
    h = h.drop_duplicates(["series_id", "timestamp_utc"], keep="first")   # Fingrid repeats ~360 quarters in Mar 2025
    first = pd.concat([inp, spot]).groupby("series_id").timestamp_utc.min()
    h = h[h.series_id.isin(first.index)]
    h = h[h.timestamp_utc < h.series_id.map(first)]
    hs, hi = h[h.series_id == "fi_spot_price"], h[h.series_id != "fi_spot_price"]
    new_inp = pd.concat([hi[inp.columns], inp], ignore_index=True).astype(inp.dtypes.to_dict())
    new_inp.to_parquet(OUT / "data/inputs.parquet", index=False)
    iso = lambda df: df.assign(**{c: df[c].dt.strftime("%Y-%m-%dT%H:%M:%SZ") for c in ("timestamp_utc", "first_usable_origin_utc")})
    pd.concat([iso(hs[spot.columns]), iso(spot)], ignore_index=True).to_csv(OUT / "data/spot_nordpool.csv", index=False)
    for f in ("actuals_validation.csv", "quality_report.md"):
        shutil.copy(PKG / "data" / f, OUT / "data" / f)
    for f in PKG.iterdir():
        if f.is_file():
            shutil.copy(f, OUT / f.name)
    print(f"{OUT}: inputs {len(new_inp):,} rows ({len(hi):,} history), spot +{len(hs):,} history rows")


if __name__ == "__main__":
    main()

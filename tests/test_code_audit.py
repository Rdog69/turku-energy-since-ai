"""Static leakage audit of the source tree (complements the runtime tests in test_availability.py).

Features must come from `SeriesIndex.value_at` / `latest`, never from positional lags or rolling
windows over a full series, and raw tables are read only inside `src/data/`. Each rule has a short
allow-list of lines that were reviewed and are not features; anything new fails until reviewed.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.features.build import (FEATURE_COLUMNS, FINGRID_RT_COLUMNS, RT_IMBALANCE_COLUMNS,
                                TARGET_COLUMNS, WEATHER_COLUMNS)
from src.models.gbm import GBMModel

SRC = Path(__file__).resolve().parents[1] / "src"

TIME_WINDOW_OPS = re.compile(r"\.(shift|rolling|expanding|ewm)\(")
RAW_TABLE_READ = re.compile(r"read_csv|read_parquet|read_feather|external_data")

# (relative path, substring of the reviewed line) -> reason
ALLOWED_WINDOW_OPS = {
    # demo sample picks the busiest days of the *forecast output*; not a model input
    ("export/demo_sample.py", "by_day.rolling("): "dashboard demo-day selection, not a feature",
    # Abdo's fetcher: gap between consecutive raw rows, to tell hourly from quarter-hourly
    # prices; availability comes from the D-1 14:00 publication rule, not from this
    ("data/external/elering_spot.py", "df.start.diff().shift(-1)"): "fetcher resolution check, not a feature",
}
ALLOWED_RAW_READS = {
    # these read templates/origins/our own forecast outputs, not input series
    ("backtest/run.py", "pd.read_csv(template"): "submission template (ids only)",
    ("backtest/run.py", "pd.read_csv(origins_csv)"): "forecast origins",
    ("export/dashboard.py", "pd.read_parquet(src)"): "our own forecast_full.parquet",
    ("export/dashboard.py", "pd.read_csv(metrics_path)"): "score summary of our own forecast",
    # Frank's pipeline (reviewed 7 Nov): none of these bypass the availability rule
    ("config.py", "HISTORY_PATH = REPO_ROOT"): "a path constant, not a read",
    ("export/map_layer.py", "pd.read_parquet(OUT_DIR / \"ecmwf_ifs025.parquet\")"): "map display; picks the newest run usable at each origin",
    ("export/map_layer.py", "pd.read_parquet(extra)"): "map display; same run selection",
    ("models/tune.py", "pd.read_parquet(path)"): "cached feature table built by build_features",
    ("models/wind_power.py", "pd.read_parquet(OUT_DIR / f)"): "weather runs wrapped in WeatherIndex (run_fu lookups); fit uses rows with fu <= cutoff",
}


def code_lines(path: Path):
    """(line number, line) of source lines that are not pure comments."""
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip().startswith("#"):
            yield n, line


def find(pattern: re.Pattern, allowed: dict, skip_data_dir: bool = False) -> list[str]:
    bad = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if skip_data_dir and rel.startswith("data/"):
            continue
        for n, line in code_lines(path):
            if pattern.search(line) and not any(rel == r and frag in line for r, frag in allowed):
                bad.append(f"src/{rel}:{n}: {line.strip()}")
    return bad


def test_no_lags_or_rolling_windows_in_src():
    bad = find(TIME_WINDOW_OPS, ALLOWED_WINDOW_OPS)
    assert not bad, "positional lags / rolling windows found (review for leakage):\n" + "\n".join(bad)


def test_raw_tables_are_read_only_in_data_package():
    bad = find(RAW_TABLE_READ, ALLOWED_RAW_READS, skip_data_dir=True)
    assert not bad, "raw tables read outside src/data/ (must go through the availability layer):\n" \
        + "\n".join(bad)


def test_no_target_columns_in_any_feature_list():
    lists = [FEATURE_COLUMNS, FINGRID_RT_COLUMNS, RT_IMBALANCE_COLUMNS, WEATHER_COLUMNS,
             GBMModel(use_weather=True, use_fingrid=True, use_rt_imbalance=True).features]
    for cols in lists:
        assert not any(c.startswith("y_") or c in TARGET_COLUMNS for c in cols)
        assert "y_first_usable" not in cols


def test_audit_catches_a_planted_lag(tmp_path):
    """The scanner itself works: a planted .shift() line is reported."""
    planted = tmp_path / "bad.py"
    planted.write_text("x = df['a'].shift(1)\n# y = df['a'].shift(2)\n")
    hits = [n for n, line in code_lines(planted) if TIME_WINDOW_OPS.search(line)]
    assert hits == [1]

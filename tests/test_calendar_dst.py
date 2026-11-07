"""DST / local-calendar check around the 25 Oct 2026 clock change (inside the test period)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.load import load_long_all
from src.features.build import build_features

try:
    LONG = load_long_all()
except FileNotFoundError:
    LONG = None

pytestmark = pytest.mark.skipif(LONG is None, reason="starter package not found")

ORIGINS = pd.date_range("2026-10-24T00:00Z", "2026-10-26T23:00Z", freq="h")


@pytest.fixture(scope="module")
def feats():
    return build_features(LONG, ORIGINS, with_targets=False)


def test_forty_unique_deliveries_per_origin(feats):
    g = feats.groupby("origin")["delivery"]
    assert (g.nunique() == 40).all()
    assert (feats.groupby("origin").size() == 40).all()


def test_calendar_matches_helsinki_local(feats):
    loc = feats["delivery"].dt.tz_convert("Europe/Helsinki")
    assert (feats["hour"] == loc.dt.hour).all()
    assert (feats["weekday"] == loc.dt.weekday).all()


def test_dst_flag_changes_at_clock_change(feats):
    if "dst" not in feats:
        pytest.skip("no dst feature")
    loc = feats["delivery"].dt.tz_convert("Europe/Helsinki")
    summer = loc.map(lambda t: t.utcoffset() == pd.Timedelta(hours=3))
    # whatever its sign convention, the flag must be constant within each offset regime
    assert feats.groupby(summer)["dst"].nunique().max() == 1


def test_all_saints_day_holiday_if_calendar_has_it():
    f = build_features(LONG, pd.DatetimeIndex(["2026-10-31T10:00Z"]), with_targets=False)
    loc = f["delivery"].dt.tz_convert("Europe/Helsinki")
    sat = f.loc[loc.dt.date == pd.Timestamp("2026-10-31").date(), "holiday"]
    if len(sat) == 0:
        pytest.skip("no 31 Oct deliveries in horizon")
    print("holiday flag on 31 Oct:", sorted(sat.unique()))
    assert sat.notna().all()

"""The live-imbalance context reaches the briefing statements, and stays spot-free."""
from __future__ import annotations

import pandas as pd

from src.explain.featherless import assert_spot_free, grid_statements
from src.export.dashboard import DRIVER_LABELS, context_for
from src.features.build import RT_IMBALANCE_COLUMNS


def test_every_rt_imbalance_column_has_a_label():
    assert all(c in DRIVER_LABELS for c in RT_IMBALANCE_COLUMNS)


def test_context_and_statements_with_fake_row():
    row = pd.Series({"wind_fc": 1000.0, "rt_sd_mean4": -350.4, "rt_plan_err_mean4": 220.0,
                     "rt_hydro_change_1h": -140.0})
    ctx = context_for(row)
    assert ctx["live_imbalance_vs_plan_mw"] == -350
    text = " ".join(grid_statements(ctx))
    assert "350 MW" in text and "BELOW" not in text.split("production")[0]
    assert "220 MW ABOVE" in text and "140 MW lower" in text
    assert_spot_free({"grid_now": grid_statements(ctx)})   # MW only, no prices


def test_statements_handle_missing_and_small_values():
    assert grid_statements({}) == []
    small = " ".join(grid_statements({"live_imbalance_vs_plan_mw": 20, "production_vs_plan_mw": 40,
                                      "hydro_change_1h_mw": 10}))
    assert "slightly" in small and "production" not in small and "Hydro" not in small
    row = pd.Series({"rt_sd_mean4": float("nan")})
    assert context_for(row).get("live_imbalance_vs_plan_mw") is None

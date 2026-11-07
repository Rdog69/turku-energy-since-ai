"""Export forecasts as static JSON for the situation-room dashboard (and its API).

    python -m src.export.dashboard --model split_fingrid --period test
    python -m src.export.dashboard --model split_fingrid --period test --demo

Output (results/dashboard/<period>/, git-ignored because it contains spot prices):

    index.json            origins, model, validation metrics
    origins/<YYYYMMDDTHH>.json  one file per forecast origin: 40 quarters, hourly blocks, alerts,
                          conflicting signals, suggestions to review, drivers, context facts
    track_record.json     daily accuracy vs simple references, each row with the time from which
                          it is known (so time travel never shows the future)

--demo writes the same structure to app_demo_data/<period>/ with the Nord Pool spot price replaced
by a synthetic curve (prices are shifted by the same amount, so gaps and probabilities stay real).
That copy contains no licensed data and can be used by the hosted Lovable preview.

All rules here are deterministic. The LLM (src/explain/) only rewrites these facts into text.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.data.availability import build_index, to_ns
from src.data.load import IMBALANCE, SPOT, load_long

TZ = "Europe/Helsinki"

DRIVER_LABELS = {
    "spot": "Spot price level", "spot_ramp_in": "Spot price jump into the quarter",
    "spot_ramp_out": "Spot price jump out of the quarter", "spot_abs_ramp": "Spot price ramp",
    "spot_minus_horizon_mean": "Spot vs. the next 10 h", "wind_fc": "Wind forecast (day-ahead)",
    "wind_fc_ramp_1h": "Wind forecast ramp", "wind_share": "Wind share of consumption",
    "cons_fc": "Consumption forecast", "solar_fc": "Solar forecast",
    "residual_load_fc": "Load not covered by wind and solar", "cap_fi_ee": "FI→EE capacity",
    "cap_ee_fi": "EE→FI capacity", "hour": "Time of day", "weekday": "Day of week",
    "holiday": "Holiday", "dst": "Summer time", "quarter": "Quarter within the hour",
    "step": "Forecast horizon", "last_gap": "Latest imbalance vs. spot",
    "mean_gap_last4": "Recent imbalance vs. spot (1 h)", "mean_gap_last8": "Recent imbalance vs. spot (2 h)",
    "last_dir": "Latest regulation direction", "mean_dir_last4": "Recent regulation direction (1 h)",
    "mean_dir_last8": "Recent regulation direction (2 h)", "last_mfrr_up_mw": "Recent mFRR up volume",
    "last_mfrr_down_mw": "Recent mFRR down volume", "last_cons_err": "Consumption vs. forecast",
    "last_flow_se1": "Flow to SE1", "last_flow_se3": "Flow to SE3", "last_flow_no4": "Flow to NO4",
    "last_flow_ee": "Flow to Estonia", "last_se1_imb_gap": "SE1 imbalance price",
    "last_se3_imb_gap": "SE3 imbalance price", "last_ee_imb_gap": "Estonia imbalance price",
    "age_q": "Age of the latest imbalance data", "rt_wind_err": "Wind now vs. day-ahead forecast",
    "rt_wind_err_last4": "Wind vs. forecast (last hour)", "rt_cons_err": "Consumption now vs. forecast",
    "rt_freq_dev": "Grid frequency deviation", "rt_freq_dev_last4": "Grid frequency (last hour)",
    "rt_nuclear": "Nuclear output", "rt_nuclear_change_6h": "Nuclear output change (6 h)",
    "om_wind_idx": "Latest weather-model wind", "om_wind_idx_da": "Weather-model wind at day-ahead time",
    "om_wind_rev": "Wind forecast revision", "om_wind_rev_mw": "Wind forecast revision (MW)",
    "om_wind_speed": "Wind speed (weather model)", "om_temp": "Temperature", "om_icing": "Icing risk",
    "om_lead_h": "Weather run age",
    # Fingrid real-time batch 2
    "rt_hydro": "Hydro output now", "rt_hydro_chg_1h": "Hydro output change (1 h)",
    "rt_boilers": "Electric boilers now", "rt_boilers_chg_1h": "Electric boilers change (1 h)",
    "rt_netimport": "Net cross-border flow now", "rt_netimport_chg_1h": "Net cross-border flow change (1 h)",
    "rt_flow_se3": "SE3 border flow now", "rt_flow_se3_chg_1h": "SE3 border flow change (1 h)",
    "rt_flow_ee": "Estonia border flow now", "rt_flow_ee_chg_1h": "Estonia border flow change (1 h)",
    "rt_chp_chg_1h": "CHP output change (1 h)",
    # 4-hour memory and the second weather model (ICON-EU)
    "mean_gap_last16": "Recent imbalance vs. spot (4 h)", "mean_dir_last16": "Recent regulation direction (4 h)",
    "om_icon_wind_idx": "Wind (second weather model)", "om_icon_wind_rev": "Wind revision (second weather model)",
    "om_model_spread": "Weather models disagree on wind",
    # Wind in the neighbouring countries (used by the median model only)
    "om_se_wind_idx": "Wind in Sweden", "om_se_wind_rev": "Wind revision in Sweden",
    "om_no_wind_idx": "Wind in Norway", "om_no_wind_rev": "Wind revision in Norway",
    "om_dk_wind_idx": "Wind in Denmark", "om_dk_wind_rev": "Wind revision in Denmark",
    "om_ee_wind_idx": "Wind in Estonia", "om_ee_wind_rev": "Wind revision in Estonia",
    "om_nordic_wind_rev": "Wind revision in neighbouring countries",
    # Learned wind production from the weather points
    "om_wind_hat": "Wind production from weather models (MW)",
    "om_wind_hat_err": "Weather models vs. day-ahead wind forecast (MW)",
    "om_wind_hat_rev": "Wind production revision since day-ahead (MW)",
    # Town weather
    "om_rad_rev": "Sunshine revision since day-ahead", "om_solar_rev_mw": "Solar production revision (MW)",
    "om_temp_town": "Temperature in the towns", "om_temp_rev": "Temperature revision since day-ahead",
    # Pricing-rule flag of models trained with the pre-June history
    "regime_2026": "Imbalance pricing rule (since June 2026)",
    # Live imbalance and plan error (Pavlo's branch, split_all_rt*)
    "rt_sd_last": "Live imbalance vs plan (now)", "rt_sd_mean4": "Live imbalance vs plan (last hour)",
    "rt_sd_trend": "Live imbalance vs plan (trend over 1 h)",
    "rt_sd_cum": "Live imbalance vs plan (cumulative)",
    "rt_plan_err": "Production vs BRP plan (now)", "rt_plan_err_mean4": "Production vs BRP plan (last hour)",
    "rt_hydro_change_1h": "Hydro output change (1 h)",
}

LEVERS = {
    "high": ("production_plan", "Check the Naantali production plan and the market position"),
    "low": ("flexible_load", "Check flexible consumption (electric boilers, heat pumps) and the market position"),
    "up": ("mfrr_up", "Review mFRR up-regulation offers"),
    "uncertain": ("position", "Check the open position: the forecast is unusually uncertain"),
}


def _z(ts) -> str:
    return pd.Timestamp(ts).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _local(ts, fmt="%H:%M") -> str:
    return pd.Timestamp(ts).tz_convert(TZ).strftime(fmt)


def _r(x, nd=1):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), nd)


def hourly_blocks(q: pd.DataFrame) -> pd.DataFrame:
    q = q.copy()
    q["block"] = (q["step"] - 1) // 4
    g = q.groupby("block")
    return pd.DataFrame({
        "start": g["delivery"].min(), "end": g["delivery"].max() + config.STEP,
        "p50": g["p50"].mean(), "spot": g["spot"].mean(), "width": (g["p90"].mean() - g["p10"].mean()),
        "p_up": g["p_up"].mean(), "spike_high": g["p_spike_high"].max(), "spike_low": g["p_spike_low"].max(),
    }).reset_index()


def alerts_for(blocks: pd.DataFrame, prev: pd.DataFrame | None, width_ref: float) -> list[dict]:
    out = []
    prev_by_start = {} if prev is None else {r.start: r for r in prev.itertuples()}
    for b in blocks.itertuples():
        win = f"{_local(b.start)}–{_local(b.end)}"
        p = prev_by_start.get(b.start)
        if b.spike_high >= 0.3 and b.spike_low >= 0.3:
            out.append({
                "type": "volatile", "severity": "medium", "start": _z(b.start), "end": _z(b.end),
                "window_local": win,
                "message": (f"Volatile hour {win}: both an exceptionally high ({b.spike_high:.0%}) and an "
                            f"exceptionally low ({b.spike_low:.0%}) price are possible."),
                "facts": {"p_spike_high": _r(b.spike_high, 3), "p_spike_low": _r(b.spike_low, 3)},
            })
        else:
            for kind, prob, label in (("high", b.spike_high, "exceptionally high"),
                                      ("low", b.spike_low, "exceptionally low")):
                delta = None if p is None else prob - (p.spike_high if kind == "high" else p.spike_low)
                rising = delta is not None and delta >= 0.15 and prob >= 0.3
                if prob >= 0.45 or rising:
                    out.append({
                        "type": f"spike_{kind}", "severity": "high" if prob >= 0.6 else "medium",
                        "start": _z(b.start), "end": _z(b.end), "window_local": win,
                        "message": (f"Risk of an {label} price {'has increased' if rising else 'is elevated'} "
                                    f"for {win} ({prob:.0%}{f', +{delta:.0%} since last hour' if rising else ''})."),
                        "facts": {"probability": _r(prob, 3), "change_since_previous": _r(delta, 3)},
                    })
        if b.p_up >= 0.65:
            out.append({"type": "up_regulation", "severity": "medium", "start": _z(b.start), "end": _z(b.end),
                        "window_local": win,
                        "message": f"Up-regulation likely for {win} ({b.p_up:.0%}): price expected above spot.",
                        "facts": {"p_up": _r(b.p_up, 3)}})
        if p is not None and abs(b.p50 - p.p50) >= 25:
            out.append({"type": "forecast_change", "severity": "medium", "start": _z(b.start), "end": _z(b.end),
                        "window_local": win,
                        # No absolute price in the text: messages go to the LLM and n8n, and an
                        # absolute forecast next to its gap would reveal the (licensed) spot price.
                        "message": f"Forecast for {win} moved {b.p50 - p.p50:+.0f} €/MWh since the previous update.",
                        "facts": {"p50": _r(b.p50), "change": _r(b.p50 - p.p50)}})
        if b.width >= 2.0 * width_ref:
            out.append({"type": "high_uncertainty", "severity": "low", "start": _z(b.start), "end": _z(b.end),
                        "window_local": win,
                        "message": f"Unusually wide range for {win}: P10–P90 spans {b.width:.0f} €/MWh.",
                        "facts": {"width": _r(b.width), "typical_width": _r(width_ref)}})
    # Keep it readable: at most 5 alerts, most severe and soonest first.
    rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda a: (rank[a["severity"]], a["start"]))
    return out[:5]


def conflicts_for(q: pd.DataFrame, blocks: pd.DataFrame) -> list[dict]:
    out = []
    first = q.iloc[0]
    b0 = blocks.iloc[0]
    if b0.p_up >= 0.6 and b0.p50 < b0.spot:
        out.append({"type": "direction_vs_price", "message":
                    "Direction model leans up-regulation, but the price forecast sits below spot.",
                    "facts": {"p_up": _r(b0.p_up, 3), "p50_minus_spot": _r(b0.p50 - b0.spot)}})
    f = first.get("rt_freq_dev")
    if f is not None and np.isfinite(f):
        if f <= -0.03 and b0.p_up < 0.4:
            out.append({"type": "frequency_vs_direction", "message":
                        "Grid frequency is low (system short now), but the next hour is forecast as down-regulation.",
                        "facts": {"freq_dev_hz": _r(f, 3), "p_up_next_hour": _r(b0.p_up, 3)}})
        if f >= 0.03 and b0.p_up > 0.6:
            out.append({"type": "frequency_vs_direction", "message":
                        "Grid frequency is high (system long now), but the next hour is forecast as up-regulation.",
                        "facts": {"freq_dev_hz": _r(f, 3), "p_up_next_hour": _r(b0.p_up, 3)}})
    rev, err = first.get("om_wind_rev_mw"), first.get("rt_wind_err")
    if rev is not None and err is not None and np.isfinite(rev) and np.isfinite(err):
        if abs(rev) >= 300 and abs(err) >= 300 and np.sign(rev) != np.sign(err):
            out.append({"type": "wind_sources_disagree", "message":
                        "The latest weather run and the measured wind point in opposite directions vs. the day-ahead forecast.",
                        "facts": {"weather_revision_mw": _r(rev, 0), "measured_wind_error_mw": _r(err, 0)}})
    return out


def suggestions_for(alerts: list[dict]) -> list[dict]:
    seen, out = set(), []
    for a in alerts:
        kind = {"spike_high": "high", "spike_low": "low", "up_regulation": "up",
                "high_uncertainty": "uncertain", "volatile": "uncertain"}.get(a["type"])
        if not kind or (kind, a["window_local"]) in seen:
            continue
        seen.add((kind, a["window_local"]))
        lever, text = LEVERS[kind]
        out.append({"lever": lever, "window_local": a["window_local"], "start": a["start"], "end": a["end"],
                    "text": f"{text} for {a['window_local']}.", "why": a["message"],
                    "note": "Suggestion to review, not an instruction: open data doesn't show available capacity, "
                            "marginal costs or existing commitments."})
    return out


def drivers_for(q: pd.DataFrame, n_steps: int = 12) -> list[dict]:
    counts: dict[str, int] = {}
    for s in q["top_drivers"].head(n_steps):
        for rank, name in enumerate(str(s).split(";")):
            if name:
                counts[name] = counts.get(name, 0) + (3 - rank)
    total = sum(counts.values()) or 1
    return [{"name": k, "label": DRIVER_LABELS.get(k, k), "weight": round(v / total, 3)}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:5]]


def context_for(row: pd.Series) -> dict:
    keys = {"wind_fc_mw": "wind_fc", "consumption_fc_mw": "cons_fc", "wind_now_vs_forecast_mw": "rt_wind_err",
            "frequency_deviation_hz": "rt_freq_dev", "nuclear_mw": "rt_nuclear",
            "nuclear_change_6h_mw": "rt_nuclear_change_6h", "latest_imbalance_vs_spot": "last_gap",
            "weather_wind_revision_mw": "om_wind_rev_mw", "icing_share": "om_icing",
            "live_imbalance_vs_plan_mw": "rt_sd_mean4", "production_vs_plan_mw": "rt_plan_err_mean4",
            "hydro_change_1h_mw": "rt_hydro_change_1h"}
    return {k: _r(row.get(v), 3 if "hz" in k or "share" in k else 0) for k, v in keys.items()
            if v in row and row.get(v) is not None}


def track_record(full: pd.DataFrame, long: pd.DataFrame) -> list[dict]:
    """Daily accuracy, each row usable from when the day's last actual is published."""
    idx = build_index(long)
    d = to_ns(full["delivery"])
    far = np.full(len(d), np.iinfo(np.int64).max)
    full = full.assign(actual=idx[IMBALANCE].value_at(d, far))
    fu = idx[IMBALANCE].first_usable_at(d)
    full = full.assign(actual_known=pd.to_datetime(np.where(fu < np.iinfo(np.int64).max, fu, 0), utc=True))
    full = full.dropna(subset=["actual"])
    # persistence reference = the latest imbalance price known at the origin (the organisers' baseline idea)
    full = full.assign(err=(full["actual"] - full["p50"]).abs(),
                       err_spot=(full["actual"] - full["spot"]).abs(),
                       err_persist=(full["actual"] - full["last_imb"]).abs() if "last_imb" in full else np.nan,
                       inside=((full["actual"] >= full["p10"]) & (full["actual"] <= full["p90"])).astype(float),
                       day=full["delivery"].dt.tz_convert(TZ).dt.date)
    rows = []
    for day, g in full.groupby("day"):
        rows.append({"day": str(day), "known_from": _z(g["actual_known"].max()), "n": int(len(g)),
                     "mae": _r(g["err"].mean(), 2), "mae_spot_only": _r(g["err_spot"].mean(), 2),
                     "mae_persistence": _r(g["err_persist"].mean(), 2), "coverage": _r(g["inside"].mean(), 3)})
    return rows


def export(model: str, period: str, demo: bool = False) -> Path:
    src = config.RESULTS_DIR / model / period / "forecast_full.parquet"
    full = pd.read_parquet(src)
    for col in ("origin", "delivery", "data_cutoff"):
        full[col] = pd.to_datetime(full[col], utc=True)
    long = load_long()
    out = (config.REPO_ROOT / "app_demo_data" / period) if demo else (config.RESULTS_DIR / "dashboard" / period)
    if out.exists():
        shutil.rmtree(out)
    (out / "origins").mkdir(parents=True)
    # Accuracy is computed on the real data (it contains no spot prices, only error statistics).
    record = track_record(full, long)

    if demo:
        # Replace spot with a synthetic daily curve and shift every price by the same amount.
        hours = full["delivery"].dt.tz_convert(TZ).dt.hour + full["delivery"].dt.minute / 60
        days = (full["delivery"] - full["delivery"].min()).dt.days
        synth = 55 + 20 * np.sin((hours - 7) / 24 * 2 * np.pi) + 8 * np.sin(days / 3.0)
        shift = synth - full["spot"]
        for c in ("p10", "p50", "p90", "last_imb"):
            if c in full:
                full[c] = full[c] + (shift if c != "last_imb" else 0)
        full["spot"] = synth
        full = full.drop(columns=["last_imb"], errors="ignore")
        for c in ("last_gap",):   # keep gaps, they're model-relevant and not spot itself
            pass

    width_ref = float((full["p90"] - full["p10"]).median())
    origins = sorted(full["origin"].unique())
    prev_blocks = None
    for o in origins:
        q = full.loc[full["origin"] == o].sort_values("step")
        blocks = hourly_blocks(q)
        alerts = alerts_for(blocks, prev_blocks, width_ref)
        doc = {
            "origin": _z(o), "origin_local": _local(o, "%Y-%m-%d %H:%M"), "data_cutoff": _z(q["data_cutoff"].iloc[0]),
            "model": model, "demo": demo,
            "quarters": [{
                "t": _z(r.delivery), "local": _local(r.delivery), "step": int(r.step),
                "p10": _r(r.p10), "p50": _r(r.p50), "p90": _r(r.p90), "spot": _r(r.spot),
                "p_up": _r(r.p_up, 3), "p_down": _r(r.p_down, 3),
                "p_spike_high": _r(r.p_spike_high, 3), "p_spike_low": _r(r.p_spike_low, 3),
                "drivers": [DRIVER_LABELS.get(n, n) for n in str(r.top_drivers).split(";") if n],
            } for r in q.itertuples()],
            "blocks": [{
                "start": _z(b.start), "end": _z(b.end), "window_local": f"{_local(b.start)}–{_local(b.end)}",
                "p50": _r(b.p50), "spot": _r(b.spot), "p_up": _r(b.p_up, 3), "spike_high": _r(b.spike_high, 3),
                "spike_low": _r(b.spike_low, 3), "width": _r(b.width)} for b in blocks.itertuples()],
            "alerts": alerts,
            "conflicts": conflicts_for(q, blocks),
            "suggestions": suggestions_for(alerts),
            "drivers": drivers_for(q),
            "context": context_for(q.iloc[0]),
            "explanation": None,   # filled by src/explain (Featherless)
        }
        # "alert" = a high-severity situation within the next 3 hours (the decision window)
        soon = pd.Timestamp(o) + pd.Timedelta(hours=3)
        status = "alert" if any(a["severity"] == "high" and pd.Timestamp(a["start"]) < soon for a in alerts) else (
            "watch" if any(a["severity"] != "low" for a in alerts) else "calm")
        doc["status"] = status
        (out / "origins" / f"{pd.Timestamp(o):%Y%m%dT%H}.json").write_text(json.dumps(doc), encoding="utf-8")
        prev_blocks = blocks

    metrics_path = config.RESULTS_DIR / model / "validation" / "score" / "score_summary.csv"
    metrics = pd.read_csv(metrics_path).to_dict("records") if metrics_path.exists() else None
    index = {"period": period, "model": model, "demo": demo, "timezone": TZ,
             "origins": [_z(o) for o in origins], "validation_metrics": metrics,
             "generated_from": str(src.relative_to(config.REPO_ROOT)).replace("\\", "/")}
    (out / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (out / "track_record.json").write_text(json.dumps(record), encoding="utf-8")
    print(f"wrote {len(origins)} origins to {out.relative_to(config.REPO_ROOT)}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="split_fingrid")
    ap.add_argument("--period", choices=["validation", "test"], default="test")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args(argv)
    export(args.model, args.period, args.demo)


if __name__ == "__main__":
    main()

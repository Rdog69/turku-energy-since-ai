"""Guard tests for the model registry in src/backtest/run.py (no fitting, runs in seconds).

1. every MODELS entry instantiates;
2. the data flags run.py reads with getattr resolve on HorizonSplit / MedianFrom and agree with
   their sub-models (catches a merge that drops a property);
3. snapshot of GBMModel.features (ordered): LightGBM column sampling depends on the column order,
   so an accidental reorder silently changes results.
   UPDATE THE SNAPSHOT ONLY ON PURPOSE, together with a docs/RESULTS.md note.
"""
import pytest

from src.backtest.run import MODELS

FLAGS = ["use_weather", "use_icon", "use_nordic", "use_wind_hat", "use_towns", "use_fingrid",
         "use_rt_imbalance", "use_history", "capacity_weighted"]

EXPECTED = {'split_all/long': ['step', 'spot', 'spot_ramp_in', 'spot_ramp_out', 'spot_abs_ramp',
                    'spot_minus_horizon_mean', 'wind_fc', 'wind_fc_ramp_1h', 'wind_share',
                    'cons_fc', 'solar_fc', 'residual_load_fc', 'cap_fi_ee', 'cap_ee_fi', 'hour',
                    'weekday', 'holiday', 'dst', 'quarter', 'last_gap', 'mean_gap_last4',
                    'mean_gap_last8', 'last_dir', 'mean_dir_last4', 'mean_dir_last8',
                    'last_mfrr_up_mw', 'last_mfrr_down_mw', 'last_cons_err', 'last_flow_se1',
                    'last_flow_se3', 'last_flow_no4', 'last_flow_ee', 'last_se1_imb_gap',
                    'last_se3_imb_gap', 'last_ee_imb_gap', 'age_q', 'om_wind_idx', 'om_wind_idx_da',
                    'om_wind_rev', 'om_wind_rev_mw', 'om_wind_speed', 'om_temp', 'om_icing',
                    'om_lead_h'],
 'split_all/short': ['step', 'spot', 'spot_ramp_in', 'spot_ramp_out', 'spot_abs_ramp',
                     'spot_minus_horizon_mean', 'wind_fc', 'wind_fc_ramp_1h', 'wind_share',
                     'cons_fc', 'solar_fc', 'residual_load_fc', 'cap_fi_ee', 'cap_ee_fi', 'hour',
                     'weekday', 'holiday', 'dst', 'quarter', 'last_gap', 'mean_gap_last4',
                     'mean_gap_last8', 'last_dir', 'mean_dir_last4', 'mean_dir_last8',
                     'last_mfrr_up_mw', 'last_mfrr_down_mw', 'last_cons_err', 'last_flow_se1',
                     'last_flow_se3', 'last_flow_no4', 'last_flow_ee', 'last_se1_imb_gap',
                     'last_se3_imb_gap', 'last_ee_imb_gap', 'age_q', 'om_wind_idx',
                     'om_wind_idx_da', 'om_wind_rev', 'om_wind_rev_mw', 'om_wind_speed', 'om_temp',
                     'om_icing', 'om_lead_h', 'rt_wind_err', 'rt_wind_err_last4', 'rt_cons_err',
                     'rt_freq_dev', 'rt_freq_dev_last4', 'rt_nuclear', 'rt_nuclear_change_6h'],
 'split_all_rt_icon/long': ['step', 'spot', 'spot_ramp_in', 'spot_ramp_out', 'spot_abs_ramp',
                            'spot_minus_horizon_mean', 'wind_fc', 'wind_fc_ramp_1h', 'wind_share',
                            'cons_fc', 'solar_fc', 'residual_load_fc', 'cap_fi_ee', 'cap_ee_fi',
                            'hour', 'weekday', 'holiday', 'dst', 'quarter', 'last_gap',
                            'mean_gap_last4', 'mean_gap_last8', 'last_dir', 'mean_dir_last4',
                            'mean_dir_last8', 'last_mfrr_up_mw', 'last_mfrr_down_mw',
                            'last_cons_err', 'last_flow_se1', 'last_flow_se3', 'last_flow_no4',
                            'last_flow_ee', 'last_se1_imb_gap', 'last_se3_imb_gap',
                            'last_ee_imb_gap', 'age_q', 'om_wind_idx', 'om_wind_idx_da',
                            'om_wind_rev', 'om_wind_rev_mw', 'om_wind_speed', 'om_temp', 'om_icing',
                            'om_lead_h', 'om_icon_wind_idx', 'om_icon_wind_rev',
                            'om_model_spread'],
 'split_all_rt_icon/short': ['step', 'spot', 'spot_ramp_in', 'spot_ramp_out', 'spot_abs_ramp',
                             'spot_minus_horizon_mean', 'wind_fc', 'wind_fc_ramp_1h', 'wind_share',
                             'cons_fc', 'solar_fc', 'residual_load_fc', 'cap_fi_ee', 'cap_ee_fi',
                             'hour', 'weekday', 'holiday', 'dst', 'quarter', 'last_gap',
                             'mean_gap_last4', 'mean_gap_last8', 'last_dir', 'mean_dir_last4',
                             'mean_dir_last8', 'last_mfrr_up_mw', 'last_mfrr_down_mw',
                             'last_cons_err', 'last_flow_se1', 'last_flow_se3', 'last_flow_no4',
                             'last_flow_ee', 'last_se1_imb_gap', 'last_se3_imb_gap',
                             'last_ee_imb_gap', 'age_q', 'om_wind_idx', 'om_wind_idx_da',
                             'om_wind_rev', 'om_wind_rev_mw', 'om_wind_speed', 'om_temp',
                             'om_icing', 'om_lead_h', 'rt_wind_err', 'rt_wind_err_last4',
                             'rt_cons_err', 'rt_freq_dev', 'rt_freq_dev_last4', 'rt_nuclear',
                             'rt_nuclear_change_6h', 'om_icon_wind_idx', 'om_icon_wind_rev',
                             'om_model_spread', 'rt_sd_last', 'rt_sd_mean4', 'rt_sd_trend',
                             'rt_sd_cum', 'rt_plan_err', 'rt_plan_err_mean4',
                             'rt_hydro_change_1h'],
 'v6_hf/base/long': ['step', 'spot', 'spot_ramp_in', 'spot_ramp_out', 'spot_abs_ramp',
                     'spot_minus_horizon_mean', 'wind_fc', 'wind_fc_ramp_1h', 'wind_share',
                     'cons_fc', 'solar_fc', 'residual_load_fc', 'cap_fi_ee', 'cap_ee_fi', 'hour',
                     'weekday', 'holiday', 'dst', 'quarter', 'last_gap', 'mean_gap_last4',
                     'mean_gap_last8', 'last_dir', 'mean_dir_last4', 'mean_dir_last8',
                     'last_mfrr_up_mw', 'last_mfrr_down_mw', 'last_cons_err', 'last_flow_se1',
                     'last_flow_se3', 'last_flow_no4', 'last_flow_ee', 'last_se1_imb_gap',
                     'last_se3_imb_gap', 'last_ee_imb_gap', 'age_q', 'om_wind_idx',
                     'om_wind_idx_da', 'om_wind_rev', 'om_wind_rev_mw', 'om_wind_speed', 'om_temp',
                     'om_icing', 'om_lead_h', 'om_icon_wind_idx', 'om_icon_wind_rev',
                     'om_model_spread', 'om_wind_hat', 'om_wind_hat_err', 'om_wind_hat_rev',
                     'regime_2026', 'mean_gap_last16', 'mean_dir_last16'],
 'v6_hf/base/short': ['step', 'spot', 'spot_ramp_in', 'spot_ramp_out', 'spot_abs_ramp',
                      'spot_minus_horizon_mean', 'wind_fc', 'wind_fc_ramp_1h', 'wind_share',
                      'cons_fc', 'solar_fc', 'residual_load_fc', 'cap_fi_ee', 'cap_ee_fi', 'hour',
                      'weekday', 'holiday', 'dst', 'quarter', 'last_gap', 'mean_gap_last4',
                      'mean_gap_last8', 'last_dir', 'mean_dir_last4', 'mean_dir_last8',
                      'last_mfrr_up_mw', 'last_mfrr_down_mw', 'last_cons_err', 'last_flow_se1',
                      'last_flow_se3', 'last_flow_no4', 'last_flow_ee', 'last_se1_imb_gap',
                      'last_se3_imb_gap', 'last_ee_imb_gap', 'age_q', 'om_wind_idx',
                      'om_wind_idx_da', 'om_wind_rev', 'om_wind_rev_mw', 'om_wind_speed', 'om_temp',
                      'om_icing', 'om_lead_h', 'rt_wind_err', 'rt_wind_err_last4', 'rt_cons_err',
                      'rt_freq_dev', 'rt_freq_dev_last4', 'rt_nuclear', 'rt_nuclear_change_6h',
                      'rt_hydro', 'rt_hydro_chg_1h', 'rt_boilers', 'rt_boilers_chg_1h',
                      'rt_netimport', 'rt_netimport_chg_1h', 'rt_flow_se3', 'rt_flow_se3_chg_1h',
                      'rt_flow_ee', 'rt_flow_ee_chg_1h', 'rt_chp_chg_1h', 'om_icon_wind_idx',
                      'om_icon_wind_rev', 'om_model_spread', 'om_wind_hat', 'om_wind_hat_err',
                      'om_wind_hat_rev', 'regime_2026', 'mean_gap_last16', 'mean_dir_last16'],
 'v6_hf/median/long': ['step', 'spot', 'spot_ramp_in', 'spot_ramp_out', 'spot_abs_ramp',
                       'spot_minus_horizon_mean', 'wind_fc', 'wind_fc_ramp_1h', 'wind_share',
                       'cons_fc', 'solar_fc', 'residual_load_fc', 'cap_fi_ee', 'cap_ee_fi', 'hour',
                       'weekday', 'holiday', 'dst', 'quarter', 'last_gap', 'mean_gap_last4',
                       'mean_gap_last8', 'last_dir', 'mean_dir_last4', 'mean_dir_last8',
                       'last_mfrr_up_mw', 'last_mfrr_down_mw', 'last_cons_err', 'last_flow_se1',
                       'last_flow_se3', 'last_flow_no4', 'last_flow_ee', 'last_se1_imb_gap',
                       'last_se3_imb_gap', 'last_ee_imb_gap', 'age_q', 'om_wind_idx',
                       'om_wind_idx_da', 'om_wind_rev', 'om_wind_rev_mw', 'om_wind_speed',
                       'om_temp', 'om_icing', 'om_lead_h', 'om_se_wind_idx', 'om_se_wind_rev',
                       'om_no_wind_idx', 'om_no_wind_rev', 'om_dk_wind_idx', 'om_dk_wind_rev',
                       'om_ee_wind_idx', 'om_ee_wind_rev', 'om_nordic_wind_rev', 'om_icon_wind_idx',
                       'om_icon_wind_rev', 'om_model_spread', 'om_wind_hat', 'om_wind_hat_err',
                       'om_wind_hat_rev', 'regime_2026', 'mean_gap_last16', 'mean_dir_last16'],
 'v6_hf/median/short': ['step', 'spot', 'spot_ramp_in', 'spot_ramp_out', 'spot_abs_ramp',
                        'spot_minus_horizon_mean', 'wind_fc', 'wind_fc_ramp_1h', 'wind_share',
                        'cons_fc', 'solar_fc', 'residual_load_fc', 'cap_fi_ee', 'cap_ee_fi', 'hour',
                        'weekday', 'holiday', 'dst', 'quarter', 'last_gap', 'mean_gap_last4',
                        'mean_gap_last8', 'last_dir', 'mean_dir_last4', 'mean_dir_last8',
                        'last_mfrr_up_mw', 'last_mfrr_down_mw', 'last_cons_err', 'last_flow_se1',
                        'last_flow_se3', 'last_flow_no4', 'last_flow_ee', 'last_se1_imb_gap',
                        'last_se3_imb_gap', 'last_ee_imb_gap', 'age_q', 'om_wind_idx',
                        'om_wind_idx_da', 'om_wind_rev', 'om_wind_rev_mw', 'om_wind_speed',
                        'om_temp', 'om_icing', 'om_lead_h', 'rt_wind_err', 'rt_wind_err_last4',
                        'rt_cons_err', 'rt_freq_dev', 'rt_freq_dev_last4', 'rt_nuclear',
                        'rt_nuclear_change_6h', 'rt_hydro', 'rt_hydro_chg_1h', 'rt_boilers',
                        'rt_boilers_chg_1h', 'rt_netimport', 'rt_netimport_chg_1h', 'rt_flow_se3',
                        'rt_flow_se3_chg_1h', 'rt_flow_ee', 'rt_flow_ee_chg_1h', 'rt_chp_chg_1h',
                        'om_se_wind_idx', 'om_se_wind_rev', 'om_no_wind_idx', 'om_no_wind_rev',
                        'om_dk_wind_idx', 'om_dk_wind_rev', 'om_ee_wind_idx', 'om_ee_wind_rev',
                        'om_nordic_wind_rev', 'om_icon_wind_idx', 'om_icon_wind_rev',
                        'om_model_spread', 'om_wind_hat', 'om_wind_hat_err', 'om_wind_hat_rev',
                        'regime_2026', 'mean_gap_last16', 'mean_dir_last16']}


def _gbms(m):
    """All leaf GBMModels of a model, in a fixed order."""
    if hasattr(m, "short"):
        return [m.short, m.long]
    if hasattr(m, "base"):
        return _gbms(m.base) + _gbms(m.median)
    return [m]


def _sub(m):
    return [getattr(m, a) for a in ("short", "long", "base", "median") if hasattr(m, a)]


def _towns(m):
    return any(getattr(m, a, False) for a in ("use_towns", "use_town_solar", "use_town_temp"))


@pytest.mark.parametrize("name", sorted(MODELS))
def test_model_instantiates_and_flags_resolve(name):
    m = MODELS[name]()
    for f in FLAGS:
        assert isinstance(getattr(m, f, False), bool), f
    subs = _sub(m)
    if not subs:
        return
    for f in FLAGS:
        if f == "capacity_weighted":
            continue
        val = getattr(m, f)
        if f == "use_towns":
            expect = any(_towns(s) or bool(getattr(s, "use_towns", False)) for s in subs)
        elif f == "use_history":
            expect = any(bool(getattr(s, f, False)) for s in subs)
        else:
            expect = any(bool(getattr(s, f, False)) for s in subs)
        assert val == expect, (name, f)


def test_known_flags():
    assert MODELS["split_all_rt_icon"]().use_rt_imbalance is True
    assert MODELS["split_all_rt_icon"]().use_icon is True
    assert MODELS["v6_hf"]().use_history is True


def _leaf(name, path):
    m = MODELS[name]()
    for p in path:
        m = getattr(m, p)
    return m


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_feature_order_snapshot(key):
    name, *path = key.split("/")
    assert list(_leaf(name, path).features) == EXPECTED[key], (
        f"{key}: feature list/order changed. If intended, update EXPECTED and add a docs/RESULTS.md note.")

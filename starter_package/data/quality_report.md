# Data quality report

- build_dataset.py version 0.1.2, schema 1.0
- Run (UTC): 2026-11-02T19:27:18Z
- Window: 2026-05-31T21:00:00Z .. 2026-11-02T06:45:00Z (quarter-hour starts, 14824 quarter-hours)
- Spot file: NordPool_HEL_local_2026-11-02.csv ({"separator": ";", "decimal": ",", "timestamp_position": "start", "rows": 14884, "days": 155, "repeated_hour_rows": 8})
- API calls: 0; cache hits 150, new responses 0

| series_id | source | dataset_id | rows | expected | missing | gap runs | longest gap (q) | duplicates removed (identical) | first | last | note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fi_imbalance_price | fingrid | 319 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z |  |
| fi_mfrr_up_price | fingrid | 244 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | mFRR energy marginal price, up |
| fi_mfrr_down_price | fingrid | 106 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | mFRR energy marginal price, down |
| fi_mfrr_up_activated | fingrid | 375 | 14823 | 14824 | 1 | 1 | 1 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | activated mFRR balancing regulation, up (max power of the quarter) |
| fi_mfrr_down_activated | fingrid | 376 | 14823 | 14824 | 1 | 1 | 1 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | activated mFRR balancing regulation, down (max power of the quarter) |
| fi_mfrr_direction | fingrid | 369 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | dominating mFRR direction: 1 up, -1 down, 0 none |
| fi_afrr_up_price | fingrid | 347 | 9974 | 14824 | 4850 | 1733 | 29 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | sparse by source: empty when there is no aFRR activation |
| fi_afrr_down_price | fingrid | 348 | 10635 | 14824 | 4189 | 1607 | 27 | 0 | 2026-05-31T21:45:00Z | 2026-11-02T06:30:00Z | sparse by source: empty when there is no aFRR activation |
| fi_consumption | fingrid | 124 | 14823 | 14824 | 1 | 1 | 1 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z |  |
| fi_production | fingrid | 74 | 14823 | 14824 | 1 | 1 | 1 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z |  |
| fi_consumption_fc_da | fingrid | 165 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | day-ahead forecast, updated once a day |
| fi_wind_fc_da | fingrid | 246 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | day-ahead forecast, updated once a day |
| fi_solar_fc_da | fingrid | 247 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | day-ahead forecast, updated once a day |
| fi_se3_flow | fingrid | 61 | 14822 | 14824 | 2 | 2 | 1 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | positive = Finland to SE3 |
| fi_no4_flow | fingrid | 57 | 14822 | 14824 | 2 | 2 | 1 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | positive = Finland to NO4 |
| fi_se1_flow | fingrid | 60 | 14822 | 14824 | 2 | 2 | 1 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | positive = Finland to SE1 |
| fi_ee_flow | fingrid | 55 | 14822 | 14824 | 2 | 2 | 1 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | positive = Finland to Estonia |
| se1_imbalance_price_long | entsoe | 17.1.g:SE1 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | imbalance price; _long = category A04 (excess balance), _short = category A05 (insufficient balance) |
| se1_imbalance_price_short | entsoe | 17.1.g:SE1 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | imbalance price; _long = category A04 (excess balance), _short = category A05 (insufficient balance) |
| se3_imbalance_price_long | entsoe | 17.1.g:SE3 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | imbalance price; _long = category A04 (excess balance), _short = category A05 (insufficient balance) |
| se3_imbalance_price_short | entsoe | 17.1.g:SE3 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | imbalance price; _long = category A04 (excess balance), _short = category A05 (insufficient balance) |
| ee_imbalance_price_long | entsoe | 17.1.g:EE | 14716 | 14824 | 108 | 11 | 24 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | imbalance price; _long = category A04 (excess balance), _short = category A05 (insufficient balance) |
| ee_imbalance_price_short | entsoe | 17.1.g:EE | 14716 | 14824 | 108 | 11 | 24 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | imbalance price; _long = category A04 (excess balance), _short = category A05 (insufficient balance) |
| se1_load_fc_da | entsoe | 6.1.b:SE1 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | day-ahead total load forecast |
| se3_load_fc_da | entsoe | 6.1.b:SE3 | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | day-ahead total load forecast |
| ee_load_fc_da | entsoe | 6.1.b:EE | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | day-ahead total load forecast; source resolution PT60M repeated to 15 min, first_usable from the original period end |
| fi_ee_capacity_da | entsoe | 11.1:FI-EE | 14824 | 14824 | 0 | 0 | 0 | 480 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | offered day-ahead implicit capacity FI to EE |
| ee_fi_capacity_da | entsoe | 11.1:EE-FI | 14824 | 14824 | 0 | 0 | 0 | 480 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | offered day-ahead implicit capacity EE to FI |
| cal_weekday_local | calendar |  | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | known in advance: first_usable_origin_utc = data period start (D17) |
| cal_hour_local | calendar |  | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | known in advance: first_usable_origin_utc = data period start (D17) |
| cal_is_holiday_fi | calendar |  | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | known in advance: first_usable_origin_utc = data period start (D17) |
| cal_is_dst | calendar |  | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | known in advance: first_usable_origin_utc = data period start (D17) |
| fi_spot_price | nordpool |  | 14824 | 14824 | 0 | 0 | 0 | 0 | 2026-05-31T21:00:00Z | 2026-11-02T06:45:00Z | Nord Pool, Turku Energia licence (D3) |
| actuals_validation.csv | actuals | 319;369;nordpool | 2688 | 2688 | 0 |  |  | 0 | 2026-09-06T21:00:00Z | 2026-10-04T20:45:00Z | missing = rows without imbalance_price; empty spot_price 0, empty direction 0 |
| actuals_test.csv | actuals | 319;369;nordpool | 2728 | 2728 | 0 |  |  | 0 | 2026-10-04T21:00:00Z | 2026-11-02T06:45:00Z | missing = rows without imbalance_price; empty spot_price 0, empty direction 0 |

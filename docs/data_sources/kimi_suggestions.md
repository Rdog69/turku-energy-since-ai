**Ranked by incremental value after your existing stack.** Hard gate: business timestamps are not publication timestamps. For every source, test September–November 2025 coverage and preserve `first_seen_at`, raw payload, model run and revisions. I cannot guarantee any provider’s 2026 retention.

1. **Energinet — Energi Data Service**  
   Catalogue: https://www.energidataservice.dk/  
   API pattern: `https://api.energidataservice.dk/dataset/{dataset}`  
   **Contains:** DK1/DK2 five-minute/hourly production, consumption, exchange, wind forecasts, and regulating-power balance, volumes and prices; separate settlement datasets.  
   **Delay:** roughly 5–15 minutes for some real-time series, hourly for forecasts, D+1 or later for settlement—measure per dataset.  
   **Licence:** free open-data service; attribution/terms apply.  
   **Why:** Danish wind errors and regulating state, especially DK2, provide an independent observation of Nordic balancing pressure. This is the lowest-risk addition. Start with real-time and regulating-power datasets, not settlement data.

2. **Svenska kraftnät and Statnett operational/balancing data — high signal, conditional**  
   https://www.svk.se/en/national-grid/the-control-room/  
   https://www.statnett.no/  
   **Contains:** Swedish/Norwegian production, consumption, exchanges and frequency; potentially balancing/mFRR reports.  
   **Delay:** live displays are approximately minute-scale where available; historical publication timing is **unsure**.  
   **Licence/API:** free web access, but supported bulk APIs, historical archives and reuse licences are **unsure**. ☐ I cannot verify a stable programmatic endpoint.  
   **Why:** probably the best additional lead for Nordic mFRR direction and FI-SE scarcity. However, a dashboard is not a qualified source: without timestamped history, use only an append-only live collector for 2026, not a reconstructed 2025 backtest.

3. **NOAA GEFS/GFS raw runs; optionally ECMWF open forecasts**  
   https://registry.opendata.aws/noaa-gefs/  
   https://registry.opendata.aws/noaa-gfs-bdp-pds/  
   https://data.ecmwf.int/forecasts/  
   **Contains:** run/step-addressable wind, temperature, pressure and cloud forecasts; GEFS supplies ensemble spread, unlike your deterministic Open-Meteo inputs.  
   **Delay:** files arrive stepwise, typically several hours after the nominal cycle; use actual object availability, never nominal run time.  
   **Licence:** NOAA data generally US-government public domain; ECMWF open data CC BY 4.0.  
   **Why:** wind-ramp and ensemble-tail probabilities should help imbalance-price spikes and mFRR direction more than another deterministic mean. Verify S3 2025 coverage and ECMWF retention before relying on either.

4. **SMHI observations and MET Norway Frost**  
   https://opendata.smhi.se/api  
   https://opendata.smhi.se/apidocs/metobs/index.html  
   https://frost.met.no/  
   **Contains:** Swedish and Norwegian station wind/gust, temperature and precipitation observations, including historical series. Frost requires free client registration.  
   **Delay:** commonly minutes to hours, station-dependent.  
   **Licence:** open data; attribution and provider/dataset terms apply.  
   **Why:** coastal-station wind nowcasts and forecast errors can proxy otherwise unavailable Swedish/Norwegian wind-generation errors.

5. **Additional ENTSO-E Transparency series**  
   `https://transparency.entsoe.eu/api`  
   **Contains:** beyond your current selection: actual generation by type, actual load, physical flows, scheduled exchanges and balancing publications for additional SE/NO/DK areas. Coverage varies substantially.  
   **Delay:** near-real-time to several days, depending on document and country.  
   **Licence:** free registration/token; ENTSO-E platform terms, not a blanket open licence.  
   **Why:** broader regional shortage and flow state can precede Finnish activation-price tails. Accept a series only if its document creation/retrieval history supports an as-of reconstruction.

6. **NVE HydAPI / Norwegian hydrology**  
   `https://hydapi.nve.no/api/v1/`  
   **Contains:** reservoir level, inflow, discharge and related observations; registration/key requirements should be checked.  
   **Delay:** minutes–hours for observations; aggregate reservoir statistics are slower, often weekly.  
   **Licence:** open; check applicable NLOD/attribution terms.  
   **Why:** useful only as a slow hydro-scarcity regime feature. Expect little incremental value at 1–40 quarter-hours.

7. **eSett Open Data**  
   https://opendata.esett.com/  
   **Contains:** published imbalance-settlement aggregates.  
   **Delay:** D+1 through later settlement revisions. Licence/API details: **unsure**.  
   **Why:** useful for offline diagnostics or sufficiently lagged regime features; generally not a live predictor.

**Highest-upside research item:** Nordic **mFRR EAM** publications could supply area-level activation prices/volumes or bid availability, directly explaining Finland’s marginal activation price. A verified free API, archive, delay and licence are **unsure**, so I would not count it as available until demonstrated.

I would deprioritise Nordic RCC publications, intraday full-depth data, lightning warnings, ice, solar and monthly district-heating/industrial statistics. Nord Pool public pages also do **not** establish free, licensed historical intraday API access.
# Real Pick Baselines By Dataset

This table collects the real-operation picking references used in the benchmark reports.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

| Dataset | Real pick source | Method | Objective | Distance | Raw recorded distance | Cross-floor correction | Floors | THMs | Pick rows | Visited nodes | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Old Full Data | `data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv` | recorded CSV + exact-style cross-floor correction | 63208.06 | 19483.06 | 18387.56 | 1095.50 | 6 | 2903 | 6255 | 1649 | available |
| New Data | `data/new_data/PickData.csv` | actual selected locations re-routed with shared route builder | 3514.04 | 1654.04 | n/a | n/a | 4 | 116 | 196 | 74 | available |
| 4000 Sample | n/a | no real-operation pick file exists for this sampled dataset | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | not available |
| 25 Item / 3 Floor | n/a | test/synthetic dataset, no real-operation benchmark source | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | not available |

Notes:

- Old Full Data uses the recorded operation file with a cross-floor correction because the raw `STEP_DIST` values understate cross-floor travel under the shared exact-style geometry.
- New Data `PickData.csv` does not include a reliable pick order, so the actually selected locations are re-routed with the shared route builder to create a comparable distance.
- 4000 Sample is derived/sample data, so there is no separate real-operation picking file for it.

# Runtime Cap Benchmark: Strict Insertion + GRASP Fallback

This report compares the same base combination under 2 minute, 5 minute, and unlimited runtime settings.

Base combination: `LK seed for 1-location articles + ascending grouped insertion + open THM shortcut`.

If a cap is reached, the partial solution is kept and remaining demand is completed with GRASP-style RCL choices.

Final route cleanup is disabled here, so the table isolates construction/fallback behavior.

Note: these are single-run measurements. The LK seed route can vary slightly between independent runs, so unlimited runs do not always dominate a capped run when the cap is not binding.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## Old Full Data

- Orders: `PickOrder.csv`
- Stock: `StockData.csv`
- Solver stock input: `StockData.csv`

| Runtime setting | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback articles | Fallback units | Strict steps | Fallback steps | Solve time |
|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | 41120.24 | 8135.24 | 6 | 2187 | 2822 | 820 | Yes | 264 | 833 | 1719 | 277 | 123.84s |
| 5 min cap + GRASP fallback | 41032.24 | 8152.24 | 6 | 2180 | 2821 | 802 | No | 0 | 0 | 1887 | 0 | 200.83s |
| Unlimited | 41146.44 | 8146.44 | 6 | 2188 | 2824 | 804 | No | 0 | 0 | 1895 | 0 | 206.23s |
| Historical actual operation | 63208.06 | 19483.06 | 6 | 2903 | 6255 | 1649 | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective in this dataset: `5 min cap + GRASP fallback` with `41032.24`.
Delta vs real-operation baseline: `-22175.82` objective points.
Real-operation source: `data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv`.

Artifacts:
- `2 min cap + GRASP fallback` pick output: [pick.csv](./benchmark_outputs/runtime_fallback/old_full_data/2min/pick.csv)
- `2 min cap + GRASP fallback` alternatives: [alt.csv](./benchmark_outputs/runtime_fallback/old_full_data/2min/alt.csv)
- `5 min cap + GRASP fallback` pick output: [pick.csv](./benchmark_outputs/runtime_fallback/old_full_data/5min/pick.csv)
- `5 min cap + GRASP fallback` alternatives: [alt.csv](./benchmark_outputs/runtime_fallback/old_full_data/5min/alt.csv)
- `Unlimited` pick output: [pick.csv](./benchmark_outputs/runtime_fallback/old_full_data/unlimited/pick.csv)
- `Unlimited` alternatives: [alt.csv](./benchmark_outputs/runtime_fallback/old_full_data/unlimited/alt.csv)

## New Data

- Orders: `NEW_DATA/OrderData.csv`
- Stock: `NEW_DATA/StockData.csv`
- Solver stock input: `benchmark_outputs/runtime_fallback/new_data/2min/normalized_stock.csv`

| Runtime setting | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback articles | Fallback units | Strict steps | Fallback steps | Solve time |
|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0 | 52 | 0 | 0.08s |
| 5 min cap + GRASP fallback | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0 | 52 | 0 | 0.07s |
| Unlimited | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0 | 52 | 0 | 0.07s |
| Real pick re-routed baseline | 3514.04 | 1654.04 | 4 | 116 | 196 | 74 | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective in this dataset: `2 min cap + GRASP fallback` with `1897.12`.
Delta vs real-operation baseline: `-1616.92` objective points.
Real-operation source: `data/new_data/PickData.csv`.

Artifacts:
- `2 min cap + GRASP fallback` pick output: [pick.csv](./benchmark_outputs/runtime_fallback/new_data/2min/pick.csv)
- `2 min cap + GRASP fallback` alternatives: [alt.csv](./benchmark_outputs/runtime_fallback/new_data/2min/alt.csv)
- `5 min cap + GRASP fallback` pick output: [pick.csv](./benchmark_outputs/runtime_fallback/new_data/5min/pick.csv)
- `5 min cap + GRASP fallback` alternatives: [alt.csv](./benchmark_outputs/runtime_fallback/new_data/5min/alt.csv)
- `Unlimited` pick output: [pick.csv](./benchmark_outputs/runtime_fallback/new_data/unlimited/pick.csv)
- `Unlimited` alternatives: [alt.csv](./benchmark_outputs/runtime_fallback/new_data/unlimited/alt.csv)

## 4000 Sample

- Orders: `4000SAMPLE/PickOrder_sample_4000.csv`
- Stock: `4000SAMPLE/StockData.csv`
- Solver stock input: `4000SAMPLE/StockData.csv`

| Runtime setting | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback articles | Fallback units | Strict steps | Fallback steps | Solve time |
|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | 32571.60 | 7371.60 | 6 | 1668 | 2077 | 671 | Yes | 15 | 56 | 1456 | 16 | 121.07s |
| 5 min cap + GRASP fallback | 32404.72 | 7309.72 | 6 | 1661 | 2076 | 671 | No | 0 | 0 | 1456 | 0 | 129.85s |
| Unlimited | 32566.28 | 7351.28 | 6 | 1669 | 2076 | 671 | No | 0 | 0 | 1464 | 0 | 132.14s |

Best objective in this dataset: `5 min cap + GRASP fallback` with `32404.72`.

Artifacts:
- `2 min cap + GRASP fallback` pick output: [pick.csv](./benchmark_outputs/runtime_fallback/4000_sample/2min/pick.csv)
- `2 min cap + GRASP fallback` alternatives: [alt.csv](./benchmark_outputs/runtime_fallback/4000_sample/2min/alt.csv)
- `5 min cap + GRASP fallback` pick output: [pick.csv](./benchmark_outputs/runtime_fallback/4000_sample/5min/pick.csv)
- `5 min cap + GRASP fallback` alternatives: [alt.csv](./benchmark_outputs/runtime_fallback/4000_sample/5min/alt.csv)
- `Unlimited` pick output: [pick.csv](./benchmark_outputs/runtime_fallback/4000_sample/unlimited/pick.csv)
- `Unlimited` alternatives: [alt.csv](./benchmark_outputs/runtime_fallback/4000_sample/unlimited/alt.csv)

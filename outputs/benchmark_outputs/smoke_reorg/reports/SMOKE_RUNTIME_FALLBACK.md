# Runtime Cap Benchmark: Strict Insertion + GRASP Fallback

This report compares the same base combination under 2 minute, 5 minute, and unlimited runtime settings.

Base combination: `LK seed for 1-location articles + ascending grouped insertion + open THM shortcut`.

If a cap is reached, the partial solution is kept and remaining demand is completed with GRASP-style RCL choices.

Final route cleanup is disabled here, so the table isolates construction/fallback behavior.

Note: these are single-run measurements. The LK seed route can vary slightly between independent runs, so unlimited runs do not always dominate a capped run when the cap is not binding.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## New Data

- Orders: `data/new_data/OrderData.csv`
- Stock: `data/new_data/StockData.csv`
- Solver stock input: `outputs/benchmark_outputs/smoke_reorg/runtime_fallback/new_data/2min/normalized_stock.csv`

| Runtime setting | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback articles | Fallback units | Strict steps | Fallback steps | Solve time |
|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0 | 52 | 0 | 0.07s |

Best objective in this dataset: `2 min cap + GRASP fallback` with `1897.12`.

Artifacts:
- `2 min cap + GRASP fallback` pick output: [pick.csv](./outputs/benchmark_outputs/smoke_reorg/runtime_fallback/new_data/2min/pick.csv)
- `2 min cap + GRASP fallback` alternatives: [alt.csv](./outputs/benchmark_outputs/smoke_reorg/runtime_fallback/new_data/2min/alt.csv)

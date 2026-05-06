# Runtime Cap + Route Cleanup Benchmark

This report starts from the runtime-capped strict insertion + GRASP fallback outputs, then applies final route cleanup variants.

Allocation is fixed within each runtime setting; only the final route order changes between `none`, `2-opt`, `swap`, and `relocate`.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## New Data

- Orders: `NEW_DATA/OrderData.csv`
- Stock: `NEW_DATA/StockData.csv`
- Solver stock input: `benchmark_outputs/runtime_fallback/new_data/2min/normalized_stock.csv`

| Runtime setting | Cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |
|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | 2-opt | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | swap | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |
| 2 min cap + GRASP fallback | relocate | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.01s | 0.09s |

Best objective in this dataset: `2 min cap + GRASP fallback + none` with `1897.12`.

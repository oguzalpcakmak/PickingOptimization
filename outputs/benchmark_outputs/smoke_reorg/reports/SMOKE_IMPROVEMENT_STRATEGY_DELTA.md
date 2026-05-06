# First vs Best Improvement Cleanup Benchmark

This report compares first-improvement and best-improvement local search on top of the runtime fallback benchmark outputs.

Allocation is fixed within each runtime setting. Only the final route cleanup strategy changes.

Definition used here: first improvement applies the first improving move found in scan order; best improvement scans the full neighborhood and applies the best improving move.

Both strategies are limited to `3` accepted moves/passes per floor to match the previous cleanup benchmark scale.

Note: this is a pure first-vs-best comparison. The earlier cleanup benchmark used a greedy pass that updated the route immediately while continuing the scan, so its numbers are not expected to match this table exactly.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## New Data

- Orders: `NEW_DATA/OrderData.csv`
- Stock: `NEW_DATA/StockData.csv`
- Solver stock input: `benchmark_outputs/runtime_fallback/new_data/2min/normalized_stock.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | none | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | swap | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |
| 2 min cap + GRASP fallback | swap | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |
| 2 min cap + GRASP fallback | relocate | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |
| 2 min cap + GRASP fallback | relocate | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |

Best objective in this dataset: `2 min cap + GRASP fallback + none + first improvement` with `1897.12`.

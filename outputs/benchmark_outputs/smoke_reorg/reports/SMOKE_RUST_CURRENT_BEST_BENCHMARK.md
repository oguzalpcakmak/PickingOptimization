# Rust Current-Best Comprehensive Benchmark

This report benchmarks the pure-Rust current-best solver across runtime budgets, cleanup operators, and first/best improvement strategies.

Pipeline: `one-location prep + pure-Rust seed route + ascending grouped strict insertion + open THM shortcut + GRASP fallback + delta-cost cleanup`.

Important difference vs Python: the Rust solver does not call the external LK package. Its seed route uses pure-Rust regret insertion plus 2-opt, so exact row-by-row routes may differ from Python.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## New Data

- Orders: `data/new_data/OrderData.csv`
- Stock: `data/new_data/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0037s | 0.0000s | 0.0037s |
| Real pick baseline | real operation | actual selected locations re-routed with shared route builder | 3514.04 | 1654.04 | 4 | 116 | 196 | 74 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective: `2 min cap + GRASP fallback + none + first improvement` with `1896.92`.
Fastest run: `2 min cap + GRASP fallback + none + first improvement` in `0.0037s`.
Delta vs real-operation baseline: `-1617.12` objective points.
Real-operation source: `data/new_data/PickData.csv`.

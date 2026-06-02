# Gurobi vs C++ Heuristic: 10-Item Benchmark

Generated: `2026-06-02T17:13:25+03:00`

## Setup

- Source orders: `data/25item3floor/PickOrder.csv`
- Source stock: `data/25item3floor/StockData.csv`
- Articles: `567, 577, 606, 609, 699, 788, 791, 866, 977, 993`
- Total pick amount: `35`
- Floors: `MZN1, MZN2, MZN3`
- Objective: `distance + 15 * THMs + 30 * active floors`
- C++ mode: `bucket-cheapest`, width `2`, LKH seed route, `2-opt best`, `3` cleanup passes
- Gurobi mode: MIP model with `--mip-gap 0` and `120s` time limit

## Results

| Solver | Status | Objective | Delta vs Gurobi optimum | Distance | Floors | THMs | Pick rows | Visited nodes | Runtime |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Corrected Gurobi MIP model | `OPTIMAL` | 423.50 | 0.00 | 243.50 | 1 | 10 | 10 | 9 | 0.4343s |
| C++ current heuristic | `COMPLETED` | 658.24 | 234.74 (55.43%) | 403.24 | 2 | 13 | 13 | 12 | 0.0460s |

## Gurobi Solve

- Best bound: `423.50`
- MIP gap: `0.0000%`
- Proven optimal: `yes`
- Variables: `1853`
- Constraints: `2068`
- Routing arcs: `1582`

## Interpretation

- Gurobi proved optimality, so the C++ delta is an exact optimality gap for this benchmark.

## Validation

- Both solver outputs reproduce the selected demand totals exactly.
- Both reported objective values were recomputed from distance, THM count, and active-floor count.
- The comparison uses the same CSV sources, article filter, floor filter, and weights.
- This run uses the current `1 / 15 / 30` project weights. Legacy `1 / 1 / 1` benchmark objectives are not directly comparable.

## Artifacts

- Run summary: `outputs/benchmark_outputs/gurobi_cpp_10item/run_summary.json`
- Gurobi summary: `outputs/benchmark_outputs/gurobi_cpp_10item/gurobi/summary.json`
- Gurobi pick output: `outputs/benchmark_outputs/gurobi_cpp_10item/gurobi/pick.csv`
- C++ summary: `outputs/benchmark_outputs/gurobi_cpp_10item/cpp_bucket_cheapest_width_2/summary.json`
- C++ pick output: `outputs/benchmark_outputs/gurobi_cpp_10item/cpp_bucket_cheapest_width_2/pick.csv`

# Gurobi vs C++ Heuristic: 25-Item / 3-Floor Benchmark

Generated: `2026-06-02T17:39:07+03:00`

## Setup

- Source orders: `data/25item3floor/PickOrder.csv`
- Source stock: `data/25item3floor/StockData.csv`
- Articles: `567, 577, 606, 609, 699, 788, 791, 866, 977, 993, 997, 999, 1019, 1020, 1030, 1051, 1055, 1061, 1066, 1068, 1087, 1088, 1093, 1118, 1122`
- Total pick amount: `71`
- Floors: `MZN1, MZN2, MZN3`
- Objective: `distance + 15 * THMs + 30 * active floors`
- C++ mode: `bucket-cheapest`, width `2`, LKH seed route, `2-opt best`, `3` cleanup passes
- Gurobi mode: MIP model with `--mip-gap 0` and `600s` time limit

## Results

| Solver | Status | Objective | Delta vs Gurobi incumbent | Distance | Floors | THMs | Pick rows | Visited nodes | Runtime |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Corrected Gurobi MIP model | `TIME_LIMIT` | 860.34 | 0.00 | 470.34 | 1 | 24 | 25 | 23 | 600.0098s |
| C++ current heuristic | `COMPLETED` | 888.42 | 28.08 (3.26%) | 498.42 | 1 | 24 | 25 | 22 | 0.0455s |

## Gurobi Solve

- Best bound: `828.66`
- MIP gap: `3.6823%`
- Proven optimal: `no`
- Variables: `9554`
- Constraints: `10072`
- Routing arcs: `8894`

## Interpretation

- Gurobi reached the time limit without proving optimality. The C++ result is `3.26%` above the Gurobi incumbent. Given the `828.66` lower bound, the C++ solution's true optimality gap is between `3.26%` and `7.21%` under this model.

## Validation

- Both solver outputs reproduce the selected demand totals exactly.
- Both reported objective values were recomputed from distance, THM count, and active-floor count.
- The comparison uses the same CSV sources, article filter, floor filter, and weights.
- This run uses the current `1 / 15 / 30` project weights. Legacy `1 / 1 / 1` benchmark objectives are not directly comparable.

## Artifacts

- Run summary: `outputs/benchmark_outputs/gurobi_cpp_25item3floor/run_summary.json`
- Gurobi summary: `outputs/benchmark_outputs/gurobi_cpp_25item3floor/gurobi/summary.json`
- Gurobi pick output: `outputs/benchmark_outputs/gurobi_cpp_25item3floor/gurobi/pick.csv`
- C++ summary: `outputs/benchmark_outputs/gurobi_cpp_25item3floor/cpp_bucket_cheapest_width_2/summary.json`
- C++ pick output: `outputs/benchmark_outputs/gurobi_cpp_25item3floor/cpp_bucket_cheapest_width_2/pick.csv`

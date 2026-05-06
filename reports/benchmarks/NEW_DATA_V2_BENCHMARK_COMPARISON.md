# New Data V2 Benchmark Comparison

This report compares the current heuristic solver variants on the updated dataset inside `NEW_DATA`.

## Input Check

- Orders used: `data/new_data/OrderData.csv`
- Stock source used for heuristics: `data/new_data/StockData.csv`
- Real-life picks used as a rerouted baseline: `data/new_data/PickData.csv`
- Column check result:
  - `OrderData.csv` matched the expected order schema: `ARTICLE_CODE, AMOUNT`
  - `data/full/StockData.csv` used `STOCK_AMOUNT` instead of `STOCK`
  - the stock file was normalized before running the solvers:
    - `outputs/benchmark_outputs/new_data_v2_5min/normalized_stock.csv`
- Feasibility check passed:
  - `77` demanded articles
  - `837` relevant candidate stock rows
  - no article had insufficient stock under the updated stock file

## Benchmark Setup

- Exact Gurobi model was intentionally excluded.
- Objective weights:
  - `distance = 1`
  - `thm = 15`
  - `floor = 30`
- Time-cap policy:
  - search-based heuristics were run with a `300s` internal search limit where supported
  - the batch harness allowed up to `360s` wall-clock per solver

## Common Comparison Metric

All solver outputs were rescored with the shared exact-style route evaluator from `heuristic_common.py`:

`Comparable Objective = Rescored Distance + 15 * Opened THMs + 30 * Active Floors`

This keeps the table fair across solvers whose internal reporting conventions differ, especially `betul-heuristic.py` and `thm_min_rr_heuristic.py`.

## Real Pick Baseline

The real-life reference file `data/new_data/PickData.csv` was rerouted with the shared heuristic route builder while keeping the actually selected locations fixed.

- Re-routed real pick comparable objective: `3514.04`
- Re-routed real pick comparable distance: `1654.04 m`
- Re-routed real pick floors: `4`
- Re-routed real pick THMs: `116`
- Re-routed real pick rows: `196`
- Re-routed real pick visited nodes: `74`

Baseline artifacts:
- `outputs/benchmark_outputs/new_data_v2_5min/real_pick_rerouted_pick.csv`
- `outputs/benchmark_outputs/new_data_v2_5min/real_pick_rerouted_alt.csv`
- `outputs/benchmark_outputs/new_data_v2_5min/real_pick_rerouted_summary.json`

## Side-by-Side Results

| Solver / Plan | Comparable Objective | Improvement vs Re-routed Real Pick | Native Reported Objective | Distance | Floors | THMs | Pick Rows | Visited Nodes | Solve Time | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Real pick re-routed baseline | 3514.04 | 0.00 | n/a | 1654.04 | 4 | 116 | 196 | 74 | 0.03s | baseline |
| GRASP multi-start | 1800.60 | 1713.44 | 1800.60 | 900.60 | 4 | 52 | 80 | 32 | 300.11s | completed |
| GRASP multi-start (no 2-opt) | 1800.60 | 1713.44 | 1800.60 | 900.60 | 4 | 52 | 80 | 32 | 300.17s | completed |
| Route-aware regret greedy | 1878.36 | 1635.68 | 1878.36 | 948.36 | 4 | 54 | 80 | 32 | 0.13s | completed |
| Large Neighborhood Search | 1882.52 | 1631.52 | 1882.52 | 1117.52 | 4 | 43 | 79 | 32 | 300.10s | completed |
| Adaptive Large Neighborhood Search | 1882.52 | 1631.52 | 1882.52 | 1117.52 | 4 | 43 | 79 | 32 | 300.11s | completed |
| Variable Neighborhood Search | 1901.00 | 1613.04 | 1901.00 | 1151.00 | 4 | 42 | 79 | 34 | 3.89s | completed |
| Fast THM-first + S-shape routing | 1993.80 | 1520.24 | 1993.80 | 1258.80 | 4 | 41 | 77 | 35 | 21.10s | completed |
| THM-min + RR-style aisle DP | 2130.44 | 1383.60 | 2100.74 | 1380.44 | 4 | 42 | 79 | 37 | 300.16s | completed |
| THM-min + S-shape routing | 2130.44 | 1383.60 | 2130.44 | 1380.44 | 4 | 42 | 79 | 37 | 300.23s | completed |
| Existing Betul heuristic | 2224.20 | 1289.84 | 6513.46 | 1264.20 | 4 | 56 | 90 | 41 | 0.13s | completed |

## Notes

- On this corrected V2 dataset, the best completed result came from `GRASP multi-start` at `1800.60`.
- `GRASP` and `GRASP (no 2-opt)` tied exactly on this instance, so the final `2-opt` cleanup did not improve the best route found in this run.
- `Route-aware regret greedy` remained extremely fast and was only `77.76` behind the best GRASP result.
- `LNS` and `ALNS` tied at `1882.52` and both used essentially the full `300s` budget.
- `VNS` again saturated early and finished in `3.89s`.
- `Fast THM-first + S-shape` opened the fewest THMs among the completed heuristics in the main group (`41`), but paid for that with a longer route.
- Both THM-min variants completed on this dataset and ended with the same rescored result.
- The re-routed real-pick baseline is `3514.04`, so every heuristic in this table improved on the real-life reference under the shared `1 / 15 / 30` objective.
- `betul-heuristic.py` again reported a much larger native objective because its internal distance accounting differs from the shared comparison metric.

## Run Artifacts

- All pick and alternative-location outputs:
  - `outputs/benchmark_outputs/new_data_v2_5min/`
- Per-solver logs:
  - `outputs/benchmark_outputs/new_data_v2_5min/logs/`
- Batch execution summary:
  - `outputs/benchmark_outputs/new_data_v2_5min/run_summary.json`

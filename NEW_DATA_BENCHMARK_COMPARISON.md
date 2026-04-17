# New-Data Benchmark Comparison

This report compares the current heuristic solver variants on the dataset inside `NEW_DATA`.

## Input Check

- Orders used: `NEW_DATA/OrderData.csv`
- Real-life picks available but not used for this run: `NEW_DATA/PickData.csv`
- Stock source used for heuristics: `NEW_DATA/StockData.csv`
- Column check result:
  - `OrderData.csv` already matched the expected order schema: `ARTICLE_CODE, AMOUNT`
  - `StockData.csv` used `STOCK_AMOUNT` instead of `STOCK`
  - The solver code reads stock rows by header name, so column order did not matter, but the stock quantity header had to be normalized
- Normalized stock file used for all runs:
  - `benchmark_outputs/new_data_5min/normalized_stock.csv`

## Benchmark Setup

- Exact Gurobi model was intentionally excluded.
- Objective weights:
  - `distance = 1`
  - `thm = 15`
  - `floor = 30`
- Time-cap policy:
  - Search-based heuristics were run with a `300s` internal search limit where supported
  - Deterministic heuristics without a built-in time-limit parameter were still run inside the same batch, but they finished far below `300s`
- Instance size after validation:
  - `77` demanded articles
  - `913` stock rows in the normalized stock file
  - `837` relevant candidate stock rows for the ordered articles
  - active floors in the input: `MZN2`, `MZN4`, `MZN5`, `MZN6`

## Common Comparison Metric

All solver outputs were rescored with the shared exact-style route evaluator from `heuristic_common.py`:

`Comparable Objective = Rescored Distance + 15 * Opened THMs + 30 * Active Floors`

This keeps the table fair across solvers whose internal reporting conventions differ, especially `betul-heuristic.py` and `thm_min_rr_heuristic.py`.

## Real Pick Baseline

The real-life reference file `NEW_DATA/PickData.csv` was rerouted with the shared heuristic route builder while keeping the actually selected locations fixed.

- Re-routed real pick comparable objective: `3514.04`
- Re-routed real pick comparable distance: `1654.04 m`
- Re-routed real pick floors: `4`
- Re-routed real pick THMs: `116`
- Re-routed real pick rows: `196`
- Re-routed real pick visited nodes: `74`

Baseline artifacts:
- `benchmark_outputs/new_data_5min/real_pick_rerouted_pick.csv`
- `benchmark_outputs/new_data_5min/real_pick_rerouted_alt.csv`
- `benchmark_outputs/new_data_5min/real_pick_rerouted_summary.json`

Note:
- This is a stronger comparison baseline than the earlier file-order estimate because `PickData.csv` does not include an explicit `PICK_ORDER` column.

## Side-by-Side Results

| Solver / Plan | Comparable Objective | Improvement vs Re-routed Real Pick | Native Reported Objective | Distance | Floors | THMs | Pick Rows | Visited Nodes | Solve Time | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Real pick re-routed baseline | 3514.04 | 0.00 | n/a | 1654.04 | 4 | 116 | 196 | 74 | 0.03s | baseline |
| GRASP multi-start | 1816.04 | 1698.00 | 1816.04 | 916.04 | 4 | 52 | 80 | 33 | 300.11s | completed |
| GRASP multi-start (no 2-opt) | 1816.04 | 1698.00 | 1816.04 | 916.04 | 4 | 52 | 80 | 33 | 300.16s | completed |
| Route-aware regret greedy | 1878.36 | 1635.68 | 1878.36 | 948.36 | 4 | 54 | 80 | 32 | 0.13s | completed |
| Large Neighborhood Search | 1905.52 | 1608.52 | 1905.52 | 1140.52 | 4 | 43 | 81 | 32 | 300.09s | completed |
| Adaptive Large Neighborhood Search | 1905.52 | 1608.52 | 1905.52 | 1140.52 | 4 | 43 | 81 | 32 | 300.11s | completed |
| Variable Neighborhood Search | 1911.04 | 1603.00 | 1911.04 | 1161.04 | 4 | 42 | 81 | 33 | 3.50s | completed |
| Fast THM-first + S-shape routing | 1990.04 | 1524.00 | 1990.04 | 1255.04 | 4 | 41 | 77 | 34 | 21.35s | completed |
| THM-min + RR-style aisle DP | 2159.24 | 1354.80 | 2126.84 | 1409.24 | 4 | 42 | 81 | 37 | 300.16s | completed |
| THM-min + S-shape routing | 2159.24 | 1354.80 | 2159.24 | 1409.24 | 4 | 42 | 81 | 37 | 300.22s | completed |
| Existing Betul heuristic | 2224.20 | 1289.84 | 6513.46 | 1264.20 | 4 | 56 | 90 | 41 | 0.13s | completed |

## Notes

- On this dataset, the best result came from `GRASP multi-start` at `1816.04`.
- The re-routed real-pick baseline is `3514.04`, so every heuristic in this table still improves on the real-life reference under the shared `1 / 15 / 30` objective.
- `GRASP` and `GRASP (no 2-opt)` tied exactly on this instance, which suggests the final `2-opt` cleanup did not change the best route found here.
- `Route-aware regret greedy` remained extremely fast and was only `62.32` behind the best GRASP result.
- `LNS` and `ALNS` tied at `1905.52` and both used essentially the full `300s` budget.
- `VNS` finished in `3.50s`, which suggests the current VNS structure saturated early on this smaller instance.
- `Fast THM-first + S-shape` opened the fewest THMs among the completed constructive heuristics in the main group (`41`), but paid for that with a longer route.
- `THM-min + RR-style` and `THM-min + S-shape` ended with the same rescored result on this dataset.
- `betul-heuristic.py` again reported a much larger native objective because its internal distance accounting differs from the shared comparison metric.

## Run Artifacts

- All pick and alternative-location outputs:
  - `benchmark_outputs/new_data_5min/`
- Per-solver logs:
  - `benchmark_outputs/new_data_5min/logs/`
- Batch execution summary:
  - `benchmark_outputs/new_data_5min/run_summary.json`

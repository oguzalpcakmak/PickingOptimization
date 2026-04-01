# Full-Data Benchmark Comparison

This report compares the current solver variants on the full order and stock data set.

## Benchmark Setup

- Orders: `PickOrder.csv`
- Stock: `StockData.csv`
- Floors: all floors in the input data (`MZN1` to `MZN6`)
- Articles: full order set
- Full instance size:
  - `2759` demanded articles
  - `24904` candidate stock locations
  - `2359` physical nodes in the exact model
- Objective weights used for the benchmark:
  - `distance = 1`
  - `thm = 15`
  - `floor = 30`

## Common Comparison Metric

The main comparison column below is `Comparable Objective`, which rescored every solver output with the same exact-style route metric:

`Comparable Objective = Rescored Distance + 15 * Opened THMs + 30 * Active Floors`

Rescored distance was computed from each exported `PICK_ORDER` sequence, floor by floor, using the shared exact-style depot-anchored distance evaluator in `heuristic_common.py`.

This matters because `betul-heuristic.py` reports a much larger native objective due to different internal distance accounting, while the exact model and the new heuristics already align to the same objective structure.

## Side-by-Side Results

| Solver / Plan | Comparable Objective | Native Reported Objective | Distance | Floors | THMs | Pick Rows | Visited Nodes | Solve Time | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Route-aware regret greedy | 41079.08 | 41079.08 | 8049.08 | 6 | 2190 | 2827 | 799 | 9.18s | Completed |
| GRASP multi-start | 41079.08 | 41079.08 | 8049.08 | 6 | 2190 | 2827 | 799 | 18.61s | Completed |
| Existing Betul heuristic | 44863.08 | 173189.96 | 9388.08 | 6 | 2353 | 2867 | 1178 | 1.86s | Completed |
| Exact Gurobi, 120s limit | 93662.44 | 93662.44 | 52412.44 | 6 | 2738 | 3156 | 915 | 120.09s | Time-limited incumbent |
| THM-min + RR-style aisle DP | n/a | n/a | n/a | n/a | n/a | n/a | n/a | ~61s before stop | DNF on full data |

## Ranking

1. Route-aware regret greedy: `41079.08`
2. GRASP multi-start: `41079.08`
3. Existing Betul heuristic: `44863.08`
4. Exact Gurobi, 120-second incumbent: `93662.44`
5. THM-min + RR-style aisle DP: no completed full-data result

## Notes

- On the full instance, `grasp_heuristic.py` matched the deterministic regret solution exactly. With its current default settings, the first elite deterministic iteration already consumes most of the search budget, so only `2` iterations completed.
- `betul-heuristic.py` remains the fastest completed solver in wall-clock time, but it is clearly weaker than the route-aware regret / GRASP solution under the common objective.
- The exact model required `--max-route-arcs 1000000` because the full instance creates `979,730` routing arcs, which exceeds the code's default safety cap of `250,000`.
- The exact run is not a fair indication of the model's ultimate solution quality. It stopped after `120.09` seconds with a very large remaining gap:
  - incumbent objective `93662.44`
  - best bound `30252.09`
  - relative gap `67.7009%`
- The THM-first + RR-style solver did not scale to the full instance in its current form. The run was stopped after about `61` seconds without producing a completed output, so it is marked as `DNF`.
- All completed heuristics were run with the same weights `1 / 15 / 30`. The exact run was also forced to those weights explicitly because `gurobi_pick_model.py` has different CLI defaults.

## Source Files

- Existing heuristic implementation: [betul-heuristic.py](./betul-heuristic.py)
- New regret heuristic: [regret_based_heuristic.py](./regret_based_heuristic.py)
- New GRASP heuristic: [grasp_heuristic.py](./grasp_heuristic.py)
- THM-min + RR-style heuristic: [thm_min_rr_heuristic.py](./thm_min_rr_heuristic.py)
- Shared heuristic utilities: [heuristic_common.py](./heuristic_common.py)

## Generated Run Artifacts

- Betul pick list: [benchmark_outputs/full_data/betul_full_pick.csv](./benchmark_outputs/full_data/betul_full_pick.csv)
- Betul alternatives: [benchmark_outputs/full_data/betul_full_alt.csv](./benchmark_outputs/full_data/betul_full_alt.csv)
- Regret pick list: [benchmark_outputs/full_data/regret_full_pick.csv](./benchmark_outputs/full_data/regret_full_pick.csv)
- Regret alternatives: [benchmark_outputs/full_data/regret_full_alt.csv](./benchmark_outputs/full_data/regret_full_alt.csv)
- GRASP pick list: [benchmark_outputs/full_data/grasp_full_pick.csv](./benchmark_outputs/full_data/grasp_full_pick.csv)
- GRASP alternatives: [benchmark_outputs/full_data/grasp_full_alt.csv](./benchmark_outputs/full_data/grasp_full_alt.csv)
- Exact 120s pick list: [benchmark_outputs/full_data/exact_full_pick.csv](./benchmark_outputs/full_data/exact_full_pick.csv)
- Exact 120s alternatives: [benchmark_outputs/full_data/exact_full_alt.csv](./benchmark_outputs/full_data/exact_full_alt.csv)

## Commands Used

### Existing Betul Heuristic

```bash
.venv/bin/python betul-heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output benchmark_outputs/full_data/betul_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/betul_full_alt.csv
```

### Route-Aware Regret Greedy

```bash
.venv/bin/python regret_based_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output benchmark_outputs/full_data/regret_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/regret_full_alt.csv
```

### GRASP Multi-Start

```bash
.venv/bin/python grasp_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output benchmark_outputs/full_data/grasp_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/grasp_full_alt.csv
```

### Exact Gurobi, 120-Second Incumbent

```bash
./run_solver.sh \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --distance-weight 1 \
  --thm-weight 15 \
  --floor-weight 30 \
  --max-route-arcs 1000000 \
  --time-limit 120 \
  --optimize \
  --pick-data-output benchmark_outputs/full_data/exact_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/exact_full_alt.csv
```

### THM-Min + RR-Style Aisle DP Attempt

```bash
.venv/bin/python thm_min_rr_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output benchmark_outputs/full_data/thm_rr_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/thm_rr_full_alt.csv
```

This last run did not finish cleanly on the full instance and therefore did not produce benchmarkable output files.

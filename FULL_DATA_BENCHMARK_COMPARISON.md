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
| Large Neighborhood Search | 36674.88 | 36674.88 | 9764.88 | 6 | 1782 | 2837 | 1116 | 6.92s | Completed |
| Adaptive Large Neighborhood Search | 36674.88 | 36674.88 | 9764.88 | 6 | 1782 | 2837 | 1116 | 6.93s | Completed |
| Variable Neighborhood Search | 36674.88 | 36674.88 | 9764.88 | 6 | 1782 | 2837 | 1116 | 7.09s | Completed |
| Fast THM-first + S-shape routing | 37135.12 | 37135.12 | 10270.12 | 6 | 1779 | 2841 | 1140 | 1.43s | Completed |
| Route-aware regret greedy | 41079.08 | 41079.08 | 8049.08 | 6 | 2190 | 2827 | 799 | 9.18s | Completed |
| GRASP multi-start | 41079.08 | 41079.08 | 8049.08 | 6 | 2190 | 2827 | 799 | 18.61s | Completed |
| GRASP multi-start (no 2-opt) | 41341.44 | 41341.44 | 8311.44 | 6 | 2190 | 2827 | 799 | 16.96s | Completed |
| Pure strict grouped cheapest insertion (no cap) | 41546.56 | 41546.56 | 8546.56 | 6 | 2188 | 2823 | 811 | 292.89s | Completed |
| 2min strict prepass + GRASP residual (no 2-opt) | 41471.56 | 41471.56 | 8546.56 | 6 | 2183 | 2824 | 821 | 209.33s | Completed |
| Strict descending grouped insertion + open THM shortcut (no cap) | 43801.56 | 43801.56 | 8821.56 | 6 | 2320 | 2820 | 887 | 102.08s | Completed |
| Existing Betul heuristic | 44863.08 | 173189.96 | 9388.08 | 6 | 2353 | 2867 | 1178 | 1.86s | Completed |
| Historical actual operation (recorded CSV) | 63208.06 | n/a | 19483.06 | 6 | 2903 | 6255 | 1649 | n/a | Historical baseline |
| Exact Gurobi, 120s limit | 93662.44 | 93662.44 | 52412.44 | 6 | 2738 | 3156 | 915 | 120.09s | Time-limited incumbent |
| THM-min + RR-style aisle DP | n/a | n/a | n/a | n/a | n/a | n/a | n/a | ~61s before stop | DNF on full data |
| THM-min + S-shape routing | n/a | n/a | n/a | n/a | n/a | n/a | n/a | not run | Not benchmarked yet |

## Additional 120-Second Neighborhood Search Runs

These reruns use the same full-data instance and the same `1 / 15 / 30` weights, but they give `lns_heuristic.py` and `alns_heuristic.py` a much larger search budget than the main table above.

| Solver / Plan | Comparable Objective | Native Reported Objective | Distance | Floors | THMs | Pick Rows | Visited Nodes | Solve Time | Delta vs 5s run |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Large Neighborhood Search, 120s | 36645.88 | 36645.88 | 9735.88 | 6 | 1782 | 2837 | 1115 | 121.89s | -29.00 |
| Adaptive Large Neighborhood Search, 120s | 36605.04 | 36605.04 | 9680.04 | 6 | 1783 | 2836 | 1110 | 121.95s | -69.84 |

## Additional 10-Minute Neighborhood Search Runs

These benchmark runs were launched with `--time-limit 600` on the same full-data instance and the same `1 / 15 / 30` weights. `vns_heuristic.py` terminated early after exhausting its current neighborhood ladder, while `lns_heuristic.py` and `alns_heuristic.py` used essentially the full budget.

| Solver / Plan | Comparable Objective | Native Reported Objective | Distance | Floors | THMs | Pick Rows | Visited Nodes | Solve Time | Delta vs 5s run |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Variable Neighborhood Search, 10min budget | 36645.88 | 36645.88 | 9735.88 | 6 | 1782 | 2837 | 1115 | 164.87s | -29.00 |
| Large Neighborhood Search, 10min budget | 36575.52 | 36575.52 | 9605.52 | 6 | 1786 | 2837 | 1105 | 601.87s | -99.36 |
| Adaptive Large Neighborhood Search, 10min budget | 36520.88 | 36520.88 | 9550.88 | 6 | 1786 | 2837 | 1100 | 602.28s | -154.00 |

## Ranking (Main Budget Runs)

1. Large / Adaptive Large / Variable Neighborhood Search: `36674.88`
2. Fast THM-first + S-shape routing: `37135.12`
3. Route-aware regret greedy: `41079.08`
4. GRASP multi-start: `41079.08`
5. GRASP multi-start (no 2-opt): `41341.44`
6. 2min strict prepass + GRASP residual (no 2-opt): `41471.56`
7. Pure strict grouped cheapest insertion (no cap): `41546.56`
8. Strict descending grouped insertion + open THM shortcut (no cap): `43801.56`
9. Existing Betul heuristic: `44863.08`
10. Historical actual operation baseline: `63208.06`
11. Exact Gurobi, 120-second incumbent: `93662.44`
12. THM-min + RR-style aisle DP: no completed full-data result
13. THM-min + S-shape routing: not benchmarked yet

## Notes

- Including the longer reruns, the current best completed full-data result in this repo is now the `10min` ALNS run at `36520.88`.
- The standalone `GRASP multi-start (no 2-opt)` rerun finished at `41341.44`, which is `262.36` worse than plain GRASP while opening the same number of THMs and floors. That gap comes entirely from longer routes, which is a clean signal that the final `2-opt` pass is materially helping on the full instance.
- The fully uncapped `Pure strict grouped cheapest insertion` benchmark finished at `41546.56` after `292.89s` (about `4.88` minutes of strict insertion plus negligible prep). It ended worse than both plain `GRASP (no 2-opt)` and the `2min strict prepass + GRASP residual` hybrid, which confirms that pushing strict insertion all the way to completion is not buying enough global quality to justify its extra runtime on this instance.
- The `Strict descending grouped insertion + open THM shortcut` variant was much faster than the ascending uncapped strict pass (`102.08s` vs `292.89s`), but it was also clearly worse on solution quality: `43801.56` objective, `2320` THMs, and `8821.56 m` distance. That is a strong signal that solving the highest-alternative articles first is a poor priority rule for this instance, even when open-THM reuse is allowed.
- The new hybrid benchmark `2min strict prepass + GRASP residual (no 2-opt)` finished at `41471.56`. It opened `7` fewer THMs than plain GRASP (`2183` vs `2190`), but its distance grew by `497.48 m`, so it finished `392.48` worse overall under the shared `1 / 15 / 30` objective.
- The phase split for that hybrid run was:
  - `120.15s` in the strict prepass
  - `88.95s` in the residual GRASP no-`2-opt` search
  - `209.33s` total
- In that same hybrid run, the 2-minute prepass fully cleared products with `2` through `22` candidate locations and partially entered the `23`-candidate group before handing the residual `251` articles to GRASP.
- The `10min` LNS rerun also improved materially, reaching `36575.52`.
- The `10min` VNS run finished early at `164.87s` and stopped at `36645.88`, which suggests the current VNS search structure saturates before the wall-clock budget on full data.
- The historical actual-operation baseline comes from `Grup_Toplama_Verisi_With_PickOrder.csv`. For consistency with the benchmark table, its comparable distance is shown as `19483.06 m` using the repo's exact-style geometry. The raw file itself records `18387.56 m`, but it underestimates cross-floor travel by `1095.50 m`.
- The `120s` LNS rerun also improved over the earlier `5s` neighborhood-search plateau, reaching `36645.88`.
- In the main `5s` budget runs, the new large-neighborhood family and VNS were tied at `36674.88` under the common `1 / 15 / 30` objective. In all three of those recorded runs, the fast THM-first seed improved from `36793.40` to `36674.88`, mainly through the shared local THM-closing moves in the seed-improvement phase.
- The fast THM-first + S-shape heuristic remains a very strong constructive baseline and is still the fastest among the stronger exact-style heuristics in this comparison.
- On the full instance, `grasp_heuristic.py` matched the deterministic regret solution exactly. With its current default settings, the first elite deterministic iteration already consumes most of the search budget, so only `2` iterations completed.
- `betul-heuristic.py` remains the fastest completed solver in wall-clock time, but it is clearly weaker than the route-aware regret / GRASP solution under the common objective.
- For VNS, the CLI `--time-limit` applies to the improvement phase. Total wall-clock also includes seed construction and the final route rebuild, which is why the `5s` benchmark run finished in about `7.09s` overall.
- For both `lns_heuristic.py` and `alns_heuristic.py`, the recorded `5s` full-data budget was effectively consumed by seed construction plus seed local descent. As a result, both runs finished with `iterations_run = 0` and simply reproduced the same post-seed solution as VNS.
- The `120s` LNS/ALNS reruns confirm that the biggest improvement opportunity is still in the shared seed local descent. Even with the larger budget, the outer loops stayed very short:
  - `LNS`: `iterations_run = 2`, no accepted post-seed destroy/repair improvement
  - `ALNS`: `iterations_run = 4`, one accepted improvement at iteration `3` via `route_cluster + balanced`
- The `10min` reruns show a clearer separation between the neighborhood-search methods:
  - `ALNS`: `68` iterations, `7` best-so-far improvements, strongest final result
  - `LNS`: `41` iterations, `5` best-so-far improvements, clearly better than the `120s` rerun
  - `VNS`: only `4` outer iterations before termination, despite the `600s` budget
- In the `10min` runs, both `LNS` and `ALNS` accepted a small THM increase from `1782` to `1786` in exchange for a much larger distance reduction, which appears to be favorable under the current `1 / 15 / 30` weighting.
- In the long-budget runs, most of the extra wall-clock was spent before the reported `lns_search` / `alns_search` phase, which means the current `phase_times` output understates how expensive the seed local descent has become on full data.
- The exact model required `--max-route-arcs 1000000` because the full instance creates `979,730` routing arcs, which exceeds the code's default safety cap of `250,000`.
- The exact run is not a fair indication of the model's ultimate solution quality. It stopped after `120.09` seconds with a very large remaining gap:
  - incumbent objective `93662.44`
  - best bound `30252.09`
  - relative gap `67.7009%`
- The THM-first + RR-style solver did not scale to the full instance in its current form. The run was stopped after about `61` seconds without producing a completed output, so it is marked as `DNF`.
- The THM-min + S-shape variant shares the same Phase 1 THM search as the RR-style solver. It has been added as a solver variant, but it has not yet been benchmarked on the full instance in this report.
- All completed heuristics were run with the same weights `1 / 15 / 30`. The exact run was also forced to those weights explicitly because `gurobi_pick_model.py` has different CLI defaults.

## Source Files

- Existing heuristic implementation: [betul-heuristic.py](./betul-heuristic.py)
- New regret heuristic: [regret_based_heuristic.py](./regret_based_heuristic.py)
- New GRASP heuristic: [grasp_heuristic.py](./grasp_heuristic.py)
- GRASP heuristic without final 2-opt: [grasp_no_two_opt_heuristic.py](./grasp_no_two_opt_heuristic.py)
- Hybrid strict+GRASP benchmark script: [hybrid_strict120_grasp_no2opt_benchmark.py](./hybrid_strict120_grasp_no2opt_benchmark.py)
- New VNS heuristic: [vns_heuristic.py](./vns_heuristic.py)
- New LNS heuristic: [lns_heuristic.py](./lns_heuristic.py)
- New ALNS heuristic: [alns_heuristic.py](./alns_heuristic.py)
- Fast THM-first + S-shape heuristic: [fast_thm_first_s_shape_heuristic.py](./fast_thm_first_s_shape_heuristic.py)
- THM-min + RR-style heuristic: [thm_min_rr_heuristic.py](./thm_min_rr_heuristic.py)
- THM-min + S-shape heuristic: [thm_min_s_shape_heuristic.py](./thm_min_s_shape_heuristic.py)
- Shared heuristic utilities: [heuristic_common.py](./heuristic_common.py)
- Shared neighborhood-search utilities: [neighborhood_search_common.py](./neighborhood_search_common.py)
- Historical operation baseline source: [Grup_Toplama_Verisi_With_PickOrder.csv](./Grup_Toplama_Verisi_With_PickOrder.csv)

## Generated Run Artifacts

- Betul pick list: [benchmark_outputs/full_data/betul_full_pick.csv](./benchmark_outputs/full_data/betul_full_pick.csv)
- Betul alternatives: [benchmark_outputs/full_data/betul_full_alt.csv](./benchmark_outputs/full_data/betul_full_alt.csv)
- Fast THM-first + S-shape pick list: [benchmark_outputs/full_data/fast_thm_sshape_full_pick.csv](./benchmark_outputs/full_data/fast_thm_sshape_full_pick.csv)
- Fast THM-first + S-shape alternatives: [benchmark_outputs/full_data/fast_thm_sshape_full_alt.csv](./benchmark_outputs/full_data/fast_thm_sshape_full_alt.csv)
- VNS pick list: [benchmark_outputs/full_data/vns_full_pick.csv](./benchmark_outputs/full_data/vns_full_pick.csv)
- VNS alternatives: [benchmark_outputs/full_data/vns_full_alt.csv](./benchmark_outputs/full_data/vns_full_alt.csv)
- LNS pick list: [benchmark_outputs/full_data/lns_full_pick.csv](./benchmark_outputs/full_data/lns_full_pick.csv)
- LNS alternatives: [benchmark_outputs/full_data/lns_full_alt.csv](./benchmark_outputs/full_data/lns_full_alt.csv)
- ALNS pick list: [benchmark_outputs/full_data/alns_full_pick.csv](./benchmark_outputs/full_data/alns_full_pick.csv)
- ALNS alternatives: [benchmark_outputs/full_data/alns_full_alt.csv](./benchmark_outputs/full_data/alns_full_alt.csv)
- LNS 120s pick list: [benchmark_outputs/full_data/lns_full_120_pick.csv](./benchmark_outputs/full_data/lns_full_120_pick.csv)
- LNS 120s alternatives: [benchmark_outputs/full_data/lns_full_120_alt.csv](./benchmark_outputs/full_data/lns_full_120_alt.csv)
- ALNS 120s pick list: [benchmark_outputs/full_data/alns_full_120_pick.csv](./benchmark_outputs/full_data/alns_full_120_pick.csv)
- ALNS 120s alternatives: [benchmark_outputs/full_data/alns_full_120_alt.csv](./benchmark_outputs/full_data/alns_full_120_alt.csv)
- VNS 10min pick list: [benchmark_outputs/full_data_t10/vns_full_t10_pick.csv](./benchmark_outputs/full_data_t10/vns_full_t10_pick.csv)
- VNS 10min alternatives: [benchmark_outputs/full_data_t10/vns_full_t10_alt.csv](./benchmark_outputs/full_data_t10/vns_full_t10_alt.csv)
- LNS 10min pick list: [benchmark_outputs/full_data_t10/lns_full_t10_pick.csv](./benchmark_outputs/full_data_t10/lns_full_t10_pick.csv)
- LNS 10min alternatives: [benchmark_outputs/full_data_t10/lns_full_t10_alt.csv](./benchmark_outputs/full_data_t10/lns_full_t10_alt.csv)
- ALNS 10min pick list: [benchmark_outputs/full_data_t10/alns_full_t10_pick.csv](./benchmark_outputs/full_data_t10/alns_full_t10_pick.csv)
- ALNS 10min alternatives: [benchmark_outputs/full_data_t10/alns_full_t10_alt.csv](./benchmark_outputs/full_data_t10/alns_full_t10_alt.csv)
- Regret pick list: [benchmark_outputs/full_data/regret_full_pick.csv](./benchmark_outputs/full_data/regret_full_pick.csv)
- Regret alternatives: [benchmark_outputs/full_data/regret_full_alt.csv](./benchmark_outputs/full_data/regret_full_alt.csv)
- GRASP pick list: [benchmark_outputs/full_data/grasp_full_pick.csv](./benchmark_outputs/full_data/grasp_full_pick.csv)
- GRASP alternatives: [benchmark_outputs/full_data/grasp_full_alt.csv](./benchmark_outputs/full_data/grasp_full_alt.csv)
- GRASP no-2-opt pick list: [benchmark_outputs/full_data/grasp_no2opt_full_pick.csv](./benchmark_outputs/full_data/grasp_no2opt_full_pick.csv)
- GRASP no-2-opt alternatives: [benchmark_outputs/full_data/grasp_no2opt_full_alt.csv](./benchmark_outputs/full_data/grasp_no2opt_full_alt.csv)
- Pure strict grouped insertion pick list: [benchmark_outputs/full_data_strict/strict_grouped_no_cap_full_pick.csv](./benchmark_outputs/full_data_strict/strict_grouped_no_cap_full_pick.csv)
- Pure strict grouped insertion alternatives: [benchmark_outputs/full_data_strict/strict_grouped_no_cap_full_alt.csv](./benchmark_outputs/full_data_strict/strict_grouped_no_cap_full_alt.csv)
- Pure strict grouped insertion summary: [benchmark_outputs/full_data_strict/strict_grouped_no_cap_summary.json](./benchmark_outputs/full_data_strict/strict_grouped_no_cap_summary.json)
- Descending strict+open-THM pick list: [benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_full_pick.csv](./benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_full_pick.csv)
- Descending strict+open-THM alternatives: [benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_full_alt.csv](./benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_full_alt.csv)
- Descending strict+open-THM summary: [benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_summary.json](./benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_summary.json)
- Hybrid pick list: [benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_pick.csv](./benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_pick.csv)
- Hybrid alternatives: [benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_alt.csv](./benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_alt.csv)
- Hybrid summary: [benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_summary.json](./benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_summary.json)
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

### Fast THM-First + S-Shape Routing

```bash
.venv/bin/python fast_thm_first_s_shape_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output benchmark_outputs/full_data/fast_thm_sshape_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/fast_thm_sshape_full_alt.csv
```

### 2min Strict Prepass + GRASP Residual (No 2-opt)

```bash
.venv/bin/python hybrid_strict120_grasp_no2opt_benchmark.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --phase1-limit 120 \
  --iterations 25 \
  --output benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_alt.csv \
  --summary-output benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_summary.json
```

### GRASP Multi-Start (No 2-opt)

```bash
.venv/bin/python grasp_no_two_opt_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output benchmark_outputs/full_data/grasp_no2opt_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/grasp_no2opt_full_alt.csv
```

### Variable Neighborhood Search

```bash
.venv/bin/python vns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 5 \
  --output benchmark_outputs/full_data/vns_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/vns_full_alt.csv
```

### Large Neighborhood Search

```bash
.venv/bin/python lns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 5 \
  --output benchmark_outputs/full_data/lns_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/lns_full_alt.csv
```

### Adaptive Large Neighborhood Search

```bash
.venv/bin/python alns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 5 \
  --output benchmark_outputs/full_data/alns_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/alns_full_alt.csv
```

### Large Neighborhood Search, 120-Second Rerun

```bash
.venv/bin/python lns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 120 \
  --output benchmark_outputs/full_data/lns_full_120_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/lns_full_120_alt.csv
```

### Adaptive Large Neighborhood Search, 120-Second Rerun

```bash
.venv/bin/python alns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 120 \
  --output benchmark_outputs/full_data/alns_full_120_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/alns_full_120_alt.csv
```

### Variable Neighborhood Search, 10-Minute Benchmark

```bash
.venv/bin/python vns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 600 \
  --output benchmark_outputs/full_data_t10/vns_full_t10_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data_t10/vns_full_t10_alt.csv
```

### Large Neighborhood Search, 10-Minute Benchmark

```bash
.venv/bin/python lns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 600 \
  --output benchmark_outputs/full_data_t10/lns_full_t10_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data_t10/lns_full_t10_alt.csv
```

### Adaptive Large Neighborhood Search, 10-Minute Benchmark

```bash
.venv/bin/python alns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 600 \
  --output benchmark_outputs/full_data_t10/alns_full_t10_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data_t10/alns_full_t10_alt.csv
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

### THM-Min + S-Shape Routing

```bash
.venv/bin/python thm_min_s_shape_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output benchmark_outputs/full_data/thm_sshape_full_pick.csv \
  --alternative-locations-output benchmark_outputs/full_data/thm_sshape_full_alt.csv
```

This variant has been added to the report for completeness, but it has not yet been benchmarked on the full instance.

## Audit Of Existing Pick-Order File

The file [Grup_Toplama_Verisi_With_PickOrder.csv](./Grup_Toplama_Verisi_With_PickOrder.csv) was also audited separately.

Using the correct route grouping key `(PICKER_CODE, PICKCAR_THM)`:

- Total recorded distance in file: `18387.56 m`
- Total recorded distance by summing final `TOTAL_DIST` per route: `18387.56 m`
- Total recorded distance by summing all `STEP_DIST`: `18387.56 m`
- Route group count: `47`
- Global unique opened THMs (`PICKED_THM`): `2903`
- Summed opened THMs across route groups: `2917`

### Audit Result

- The file is internally consistent.
- `TOTAL_DIST` and `STEP_DIST` agree exactly.
- Same-node repeat rows correctly use `STEP_DIST = 0`.
- All same-floor movement rows match the shared warehouse geometry exactly.
- The only mismatches come from cross-floor transitions.

### Cross-Floor Difference

Under the shared exact-style warehouse metric used elsewhere in this repo:

- Same-floor recorded distance: `16982.04 m`
- Same-floor recalculated distance: `16982.04 m`
- Cross-floor recorded distance: `1405.52 m`
- Cross-floor recalculated distance: `2501.02 m`
- Cross-floor mismatch count: `19`

So the file appears to use a simplified cross-floor transition rule. It is accurate for same-floor routing, but it underestimates cross-floor travel by `1095.50 m` relative to the repo's exact-model geometry.

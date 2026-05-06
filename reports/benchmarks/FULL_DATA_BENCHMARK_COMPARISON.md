# Full-Data Benchmark Comparison

This report compares the current solver variants on the full order and stock data set.

## Benchmark Setup

- Orders: `data/full/PickOrder.csv`
- Stock: `data/full/StockData.csv`
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
| Route-aware regret + LK2 routing | 40832.32 | 40832.32 | 7802.32 | 6 | 2190 | 2827 | 799 | 7.42s | Completed |
| LK seed for 1-location articles + ascending grouped insertion + open THM shortcut | 41018.72 | 41018.72 | 8183.72 | 6 | 2177 | 2823 | 810 | 206.32s | Completed |
| Route-aware regret greedy | 41079.08 | 41079.08 | 8049.08 | 6 | 2190 | 2827 | 799 | 9.18s | Completed |
| GRASP multi-start | 41079.08 | 41079.08 | 8049.08 | 6 | 2190 | 2827 | 799 | 18.61s | Completed |
| Route-aware regret + imported city swap routing | 41306.64 | 41306.64 | 8276.64 | 6 | 2190 | 2827 | 799 | 7.93s | Completed |
| GRASP multi-start (no 2-opt) | 41341.44 | 41341.44 | 8311.44 | 6 | 2190 | 2827 | 799 | 16.96s | Completed |
| Route-aware regret + imported simulated annealing routing | 41341.44 | 41341.44 | 8311.44 | 6 | 2190 | 2827 | 799 | 10.55s | Completed |
| Route-aware regret + imported genetic routing | 41341.44 | 41341.44 | 8311.44 | 6 | 2190 | 2827 | 799 | 7.33s | Completed |
| Pure strict grouped cheapest insertion (no cap) | 41546.56 | 41546.56 | 8546.56 | 6 | 2188 | 2823 | 811 | 292.89s | Completed |
| 2min strict prepass + GRASP residual (no 2-opt) | 41471.56 | 41471.56 | 8546.56 | 6 | 2183 | 2824 | 821 | 209.33s | Completed |
| Strict descending grouped insertion + open THM shortcut (no cap) | 43801.56 | 43801.56 | 8821.56 | 6 | 2320 | 2820 | 887 | 102.08s | Completed |
| Existing Betul heuristic | 44863.08 | 173189.96 | 9388.08 | 6 | 2353 | 2867 | 1178 | 1.86s | Completed |
| GTSP Genetic Algorithm (cap 4) | 43851.20 | 43851.20 | 8901.20 | 6 | 2318 | 2786 | 963 | 10.79s | Completed |
| GTSP Tabu Search (cap 4) | 43973.68 | 43973.68 | 9023.68 | 6 | 2318 | 2786 | 964 | 11.17s | Completed |
| GTSP Ant Colony (cap 4) | 44071.56 | 44071.56 | 9121.56 | 6 | 2318 | 2786 | 963 | 134.77s | Completed |
| GTSP Simulated Annealing (cap 4) | 44143.76 | 44143.76 | 9193.76 | 6 | 2318 | 2786 | 963 | 11.04s | Completed |
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
3. Route-aware regret + LK2 routing: `40832.32`
4. LK seed for 1-location articles + ascending grouped insertion + open THM shortcut: `41018.72`
5. Route-aware regret greedy: `41079.08`
6. GRASP multi-start: `41079.08`
7. Route-aware regret + imported city swap routing: `41306.64`
8. GRASP multi-start (no 2-opt): `41341.44`
9. Route-aware regret + imported simulated annealing routing: `41341.44`
10. Route-aware regret + imported genetic routing: `41341.44`
11. 2min strict prepass + GRASP residual (no 2-opt): `41471.56`
12. Pure strict grouped cheapest insertion (no cap): `41546.56`
13. Strict descending grouped insertion + open THM shortcut (no cap): `43801.56`
14. GTSP Genetic Algorithm (cap 4): `43851.20`
15. GTSP Tabu Search (cap 4): `43973.68`
16. GTSP Ant Colony (cap 4): `44071.56`
17. GTSP Simulated Annealing (cap 4): `44143.76`
18. Existing Betul heuristic: `44863.08`
19. Historical actual operation baseline: `63208.06`
20. Exact Gurobi, 120-second incumbent: `93662.44`
21. THM-min + RR-style aisle DP: no completed full-data result
22. THM-min + S-shape routing: not benchmarked yet

## Notes

- Including the longer reruns, the current best completed full-data result in this repo is now the `10min` ALNS run at `36520.88`.
- The imported `lk_heuristic` package was integrated as a warehouse-aware per-floor route optimizer on top of the deterministic regret allocation. Using the package's `lk2_improve` search lowered the full-data objective from `41079.08` to `40832.32`, a pure route-distance gain of `246.76` with the same `2190` THMs, `6` floors, `2827` pick rows, and `799` visited nodes.
- That LK-routed regret run also finished faster than the old regret baseline on this instance (`7.42s` vs `9.18s`). In this integration, the imported package is improving route order only; location/THM selection still comes from the repo's regret allocator.
- The new `LK seed for 1-location articles + ascending grouped insertion + open THM shortcut` benchmark reached `41018.72`, which is `60.36` better than plain `GRASP` and the deterministic regret baseline. It opened `13` fewer THMs (`2177` vs `2190`) while adding only `134.64 m` of distance, so the THM savings were enough to improve the shared `1 / 15 / 30` objective.
- In that benchmark, the LK seed itself was essentially free (`0.12s` total across all floors). Almost all runtime still came from the ascending grouped insertion phase (`206.17s`), which suggests the quality gain came from handing the grouped phase a better initial route backbone for the single-location picks.
- The imported TSP trio from `3-heuristic-algorithms-in-Python-for-Travelling-Salesman-Problem-main` was also adapted as route-only post-optimizers on top of the same regret allocation. None of those three improved the base regret route on full data.
- Their full-data results were:
  - imported city swap: `41306.64`
  - imported simulated annealing: `41341.44`
  - imported genetic: `41341.44`
- The best of that group, `imported city swap`, still finished `227.56` worse than plain regret and `474.32` worse than the LK-routed regret variant. All three kept the same `2190` THMs and `6` floors, so the gap is entirely route-distance quality.
- During integration, the imported genetic logic needed a guard against population collapse. Without that, parent selection could stall while trying to draw more unique parents than the degenerated population still contained.
- The GTSP-family full-data benchmark was rerun after two warehouse-specific improvements: a regret-seeded initial path and a warehouse-aware construction objective during search. The refreshed benchmark also widened the shared GTSP candidate cap from `2` to `4` per article.
- That update improved the best GTSP result from the earlier `46870.56` down to `43851.20`, a gain of `3019.36` objective points.
- In the refreshed GTSP benchmark, `GTSP Genetic Algorithm (cap 4)` is the strongest variant at `43851.20`. That is `1011.88` better than the legacy `betul-heuristic.py` baseline and only `49.64` worse than `Strict descending grouped insertion + open THM shortcut (no cap)`.
- All four refreshed GTSP variants converged to a much tighter band than before and, notably, to the same `2318` opened THMs. The remaining quality differences in that family now come mostly from route distance rather than THM count.
- The imported GTSP ant-colony method remains the most expensive GTSP variant on full data. Even with only `1` ant and `1` iteration, the seeded cap-4 run still took `134.77s`, while the other GTSP variants finished in about `10.79s` to `11.17s`.
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
- LK-routed warehouse heuristic: [lk_warehouse_heuristic.py](./lk_warehouse_heuristic.py)
- LK-seeded ascending grouped benchmark script: [lk_seed_one_loc_ascending_open_thm_benchmark.py](./lk_seed_one_loc_ascending_open_thm_benchmark.py)
- LK full-data benchmark runner: [benchmark_lk_full_data.py](./benchmark_lk_full_data.py)
- Imported LK core: [lk_heuristic-master/src/lk_heuristic/models/tsp.py](./lk_heuristic-master/src/lk_heuristic/models/tsp.py)
- Imported TSP warehouse heuristic: [imported_tsp_warehouse_heuristic.py](./imported_tsp_warehouse_heuristic.py)
- Imported TSP route adapters: [imported_tsp_route_optimizers.py](./imported_tsp_route_optimizers.py)
- Imported TSP full-data benchmark runner: [benchmark_imported_tsp_full_data.py](./benchmark_imported_tsp_full_data.py)
- Imported TSP source folder: [3-heuristic-algorithms-in-Python-for-Travelling-Salesman-Problem-main](./3-heuristic-algorithms-in-Python-for-Travelling-Salesman-Problem-main)
- New GRASP heuristic: [grasp_heuristic.py](./grasp_heuristic.py)
- GRASP heuristic without final 2-opt: [grasp_no_two_opt_heuristic.py](./grasp_no_two_opt_heuristic.py)
- Hybrid strict+GRASP benchmark script: [hybrid_strict120_grasp_no2opt_benchmark.py](./hybrid_strict120_grasp_no2opt_benchmark.py)
- New VNS heuristic: [vns_heuristic.py](./vns_heuristic.py)
- New LNS heuristic: [lns_heuristic.py](./lns_heuristic.py)
- New ALNS heuristic: [alns_heuristic.py](./alns_heuristic.py)
- Fast THM-first + S-shape heuristic: [fast_thm_first_s_shape_heuristic.py](./fast_thm_first_s_shape_heuristic.py)
- GTSP full-data benchmark runner: [benchmark_gtsp_full_data.py](./benchmark_gtsp_full_data.py)
- GTSP warehouse CLI runner: [gtsp_warehouse_solver.py](./gtsp_warehouse_solver.py)
- GTSP warehouse adapter: [GTSP-master/warehouse_problem.py](./GTSP-master/warehouse_problem.py)
- GTSP imported algorithm implementations:
  - [GTSP-master/Algorithms/Annealing.py](./GTSP-master/Algorithms/Annealing.py)
  - [GTSP-master/Algorithms/Antcolony.py](./GTSP-master/Algorithms/Antcolony.py)
  - [GTSP-master/Algorithms/Genetic.py](./GTSP-master/Algorithms/Genetic.py)
  - [GTSP-master/Algorithms/Tabu.py](./GTSP-master/Algorithms/Tabu.py)
- THM-min + RR-style heuristic: [thm_min_rr_heuristic.py](./thm_min_rr_heuristic.py)
- THM-min + S-shape heuristic: [thm_min_s_shape_heuristic.py](./thm_min_s_shape_heuristic.py)
- Shared heuristic utilities: [heuristic_common.py](./heuristic_common.py)
- Shared neighborhood-search utilities: [neighborhood_search_common.py](./neighborhood_search_common.py)
- Historical operation baseline source: [Grup_Toplama_Verisi_With_PickOrder.csv](../../data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv)

## Generated Run Artifacts

- Betul pick list: [benchmark_outputs/full_data/betul_full_pick.csv](../../outputs/benchmark_outputs/full_data/betul_full_pick.csv)
- Betul alternatives: [benchmark_outputs/full_data/betul_full_alt.csv](../../outputs/benchmark_outputs/full_data/betul_full_alt.csv)
- Fast THM-first + S-shape pick list: [benchmark_outputs/full_data/fast_thm_sshape_full_pick.csv](../../outputs/benchmark_outputs/full_data/fast_thm_sshape_full_pick.csv)
- Fast THM-first + S-shape alternatives: [benchmark_outputs/full_data/fast_thm_sshape_full_alt.csv](../../outputs/benchmark_outputs/full_data/fast_thm_sshape_full_alt.csv)
- LK benchmark summary: [benchmark_outputs/full_data_lk/run_summary.json](../../outputs/benchmark_outputs/full_data_lk/run_summary.json)
- LK-routed regret pick list: [benchmark_outputs/full_data_lk/lk_regret_full_pick.csv](../../outputs/benchmark_outputs/full_data_lk/lk_regret_full_pick.csv)
- LK-routed regret alternatives: [benchmark_outputs/full_data_lk/lk_regret_full_alt.csv](../../outputs/benchmark_outputs/full_data_lk/lk_regret_full_alt.csv)
- LK-seeded ascending pick list: [benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_pick.csv](../../outputs/benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_pick.csv)
- LK-seeded ascending alternatives: [benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_alt.csv](../../outputs/benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_alt.csv)
- LK-seeded ascending summary: [benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_summary.json](../../outputs/benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_summary.json)
- Imported TSP benchmark summary: [benchmark_outputs/full_data_imported_tsp/run_summary.json](../../outputs/benchmark_outputs/full_data_imported_tsp/run_summary.json)
- Imported city swap pick list: [benchmark_outputs/full_data_imported_tsp/imported_city_swap_full_pick.csv](../../outputs/benchmark_outputs/full_data_imported_tsp/imported_city_swap_full_pick.csv)
- Imported city swap alternatives: [benchmark_outputs/full_data_imported_tsp/imported_city_swap_full_alt.csv](../../outputs/benchmark_outputs/full_data_imported_tsp/imported_city_swap_full_alt.csv)
- Imported simulated annealing pick list: [benchmark_outputs/full_data_imported_tsp/imported_sa_full_pick.csv](../../outputs/benchmark_outputs/full_data_imported_tsp/imported_sa_full_pick.csv)
- Imported simulated annealing alternatives: [benchmark_outputs/full_data_imported_tsp/imported_sa_full_alt.csv](../../outputs/benchmark_outputs/full_data_imported_tsp/imported_sa_full_alt.csv)
- Imported genetic pick list: [benchmark_outputs/full_data_imported_tsp/imported_genetic_full_pick.csv](../../outputs/benchmark_outputs/full_data_imported_tsp/imported_genetic_full_pick.csv)
- Imported genetic alternatives: [benchmark_outputs/full_data_imported_tsp/imported_genetic_full_alt.csv](../../outputs/benchmark_outputs/full_data_imported_tsp/imported_genetic_full_alt.csv)
- GTSP benchmark summary: [benchmark_outputs/full_data_gtsp/run_summary.json](../../outputs/benchmark_outputs/full_data_gtsp/run_summary.json)
- GTSP annealing pick list: [benchmark_outputs/full_data_gtsp/gtsp_annealing_pick.csv](../../outputs/benchmark_outputs/full_data_gtsp/gtsp_annealing_pick.csv)
- GTSP annealing alternatives: [benchmark_outputs/full_data_gtsp/gtsp_annealing_alt.csv](../../outputs/benchmark_outputs/full_data_gtsp/gtsp_annealing_alt.csv)
- GTSP tabu pick list: [benchmark_outputs/full_data_gtsp/gtsp_tabu_pick.csv](../../outputs/benchmark_outputs/full_data_gtsp/gtsp_tabu_pick.csv)
- GTSP tabu alternatives: [benchmark_outputs/full_data_gtsp/gtsp_tabu_alt.csv](../../outputs/benchmark_outputs/full_data_gtsp/gtsp_tabu_alt.csv)
- GTSP genetic pick list: [benchmark_outputs/full_data_gtsp/gtsp_genetic_pick.csv](../../outputs/benchmark_outputs/full_data_gtsp/gtsp_genetic_pick.csv)
- GTSP genetic alternatives: [benchmark_outputs/full_data_gtsp/gtsp_genetic_alt.csv](../../outputs/benchmark_outputs/full_data_gtsp/gtsp_genetic_alt.csv)
- GTSP ant colony pick list: [benchmark_outputs/full_data_gtsp/gtsp_antcolony_pick.csv](../../outputs/benchmark_outputs/full_data_gtsp/gtsp_antcolony_pick.csv)
- GTSP ant colony alternatives: [benchmark_outputs/full_data_gtsp/gtsp_antcolony_alt.csv](../../outputs/benchmark_outputs/full_data_gtsp/gtsp_antcolony_alt.csv)
- VNS pick list: [benchmark_outputs/full_data/vns_full_pick.csv](../../outputs/benchmark_outputs/full_data/vns_full_pick.csv)
- VNS alternatives: [benchmark_outputs/full_data/vns_full_alt.csv](../../outputs/benchmark_outputs/full_data/vns_full_alt.csv)
- LNS pick list: [benchmark_outputs/full_data/lns_full_pick.csv](../../outputs/benchmark_outputs/full_data/lns_full_pick.csv)
- LNS alternatives: [benchmark_outputs/full_data/lns_full_alt.csv](../../outputs/benchmark_outputs/full_data/lns_full_alt.csv)
- ALNS pick list: [benchmark_outputs/full_data/alns_full_pick.csv](../../outputs/benchmark_outputs/full_data/alns_full_pick.csv)
- ALNS alternatives: [benchmark_outputs/full_data/alns_full_alt.csv](../../outputs/benchmark_outputs/full_data/alns_full_alt.csv)
- LNS 120s pick list: [benchmark_outputs/full_data/lns_full_120_pick.csv](../../outputs/benchmark_outputs/full_data/lns_full_120_pick.csv)
- LNS 120s alternatives: [benchmark_outputs/full_data/lns_full_120_alt.csv](../../outputs/benchmark_outputs/full_data/lns_full_120_alt.csv)
- ALNS 120s pick list: [benchmark_outputs/full_data/alns_full_120_pick.csv](../../outputs/benchmark_outputs/full_data/alns_full_120_pick.csv)
- ALNS 120s alternatives: [benchmark_outputs/full_data/alns_full_120_alt.csv](../../outputs/benchmark_outputs/full_data/alns_full_120_alt.csv)
- VNS 10min pick list: [benchmark_outputs/full_data_t10/vns_full_t10_pick.csv](../../outputs/benchmark_outputs/full_data_t10/vns_full_t10_pick.csv)
- VNS 10min alternatives: [benchmark_outputs/full_data_t10/vns_full_t10_alt.csv](../../outputs/benchmark_outputs/full_data_t10/vns_full_t10_alt.csv)
- LNS 10min pick list: [benchmark_outputs/full_data_t10/lns_full_t10_pick.csv](../../outputs/benchmark_outputs/full_data_t10/lns_full_t10_pick.csv)
- LNS 10min alternatives: [benchmark_outputs/full_data_t10/lns_full_t10_alt.csv](../../outputs/benchmark_outputs/full_data_t10/lns_full_t10_alt.csv)
- ALNS 10min pick list: [benchmark_outputs/full_data_t10/alns_full_t10_pick.csv](../../outputs/benchmark_outputs/full_data_t10/alns_full_t10_pick.csv)
- ALNS 10min alternatives: [benchmark_outputs/full_data_t10/alns_full_t10_alt.csv](../../outputs/benchmark_outputs/full_data_t10/alns_full_t10_alt.csv)
- Regret pick list: [benchmark_outputs/full_data/regret_full_pick.csv](../../outputs/benchmark_outputs/full_data/regret_full_pick.csv)
- Regret alternatives: [benchmark_outputs/full_data/regret_full_alt.csv](../../outputs/benchmark_outputs/full_data/regret_full_alt.csv)
- GRASP pick list: [benchmark_outputs/full_data/grasp_full_pick.csv](../../outputs/benchmark_outputs/full_data/grasp_full_pick.csv)
- GRASP alternatives: [benchmark_outputs/full_data/grasp_full_alt.csv](../../outputs/benchmark_outputs/full_data/grasp_full_alt.csv)
- GRASP no-2-opt pick list: [benchmark_outputs/full_data/grasp_no2opt_full_pick.csv](../../outputs/benchmark_outputs/full_data/grasp_no2opt_full_pick.csv)
- GRASP no-2-opt alternatives: [benchmark_outputs/full_data/grasp_no2opt_full_alt.csv](../../outputs/benchmark_outputs/full_data/grasp_no2opt_full_alt.csv)
- Pure strict grouped insertion pick list: [benchmark_outputs/full_data_strict/strict_grouped_no_cap_full_pick.csv](../../outputs/benchmark_outputs/full_data_strict/strict_grouped_no_cap_full_pick.csv)
- Pure strict grouped insertion alternatives: [benchmark_outputs/full_data_strict/strict_grouped_no_cap_full_alt.csv](../../outputs/benchmark_outputs/full_data_strict/strict_grouped_no_cap_full_alt.csv)
- Pure strict grouped insertion summary: [benchmark_outputs/full_data_strict/strict_grouped_no_cap_summary.json](../../outputs/benchmark_outputs/full_data_strict/strict_grouped_no_cap_summary.json)
- Descending strict+open-THM pick list: [benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_full_pick.csv](../../outputs/benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_full_pick.csv)
- Descending strict+open-THM alternatives: [benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_full_alt.csv](../../outputs/benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_full_alt.csv)
- Descending strict+open-THM summary: [benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_summary.json](../../outputs/benchmark_outputs/full_data_desc_openthm/strict_desc_open_thm_no_cap_summary.json)
- Hybrid pick list: [benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_pick.csv](../../outputs/benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_pick.csv)
- Hybrid alternatives: [benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_alt.csv](../../outputs/benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_alt.csv)
- Hybrid summary: [benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_summary.json](../../outputs/benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_summary.json)
- Exact 120s pick list: [benchmark_outputs/full_data/exact_full_pick.csv](../../outputs/benchmark_outputs/full_data/exact_full_pick.csv)
- Exact 120s alternatives: [benchmark_outputs/full_data/exact_full_alt.csv](../../outputs/benchmark_outputs/full_data/exact_full_alt.csv)

## Commands Used

### Existing Betul Heuristic

```bash
.venv/bin/python betul-heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output outputs/benchmark_outputs/full_data/betul_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/betul_full_alt.csv
```

### Route-Aware Regret Greedy

```bash
.venv/bin/python regret_based_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output outputs/benchmark_outputs/full_data/regret_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/regret_full_alt.csv
```

### Route-Aware Regret + LK2 Routing

```bash
python benchmark_lk_full_data.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output-dir outputs/benchmark_outputs/full_data_lk \
  --summary-output outputs/benchmark_outputs/full_data_lk/run_summary.json
```

### LK Seed For 1-Location Articles + Ascending Grouped Insertion

```bash
.venv/bin/python lk_seed_one_loc_ascending_open_thm_benchmark.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output outputs/benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_alt.csv \
  --summary-output outputs/benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_summary.json
```

### Imported TSP Route Post-Optimizers

```bash
python benchmark_imported_tsp_full_data.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output-dir outputs/benchmark_outputs/full_data_imported_tsp \
  --summary-output outputs/benchmark_outputs/full_data_imported_tsp/run_summary.json
```

### Fast THM-First + S-Shape Routing

```bash
.venv/bin/python fast_thm_first_s_shape_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output outputs/benchmark_outputs/full_data/fast_thm_sshape_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/fast_thm_sshape_full_alt.csv
```

### GTSP Family Full-Data Benchmark

```bash
python benchmark_gtsp_full_data.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output-dir outputs/benchmark_outputs/full_data_gtsp \
  --summary-output outputs/benchmark_outputs/full_data_gtsp/run_summary.json
```

### 2min Strict Prepass + GRASP Residual (No 2-opt)

```bash
.venv/bin/python hybrid_strict120_grasp_no2opt_benchmark.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --phase1-limit 120 \
  --iterations 25 \
  --output outputs/benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_alt.csv \
  --summary-output outputs/benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_summary.json
```

### GRASP Multi-Start (No 2-opt)

```bash
.venv/bin/python grasp_no_two_opt_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output outputs/benchmark_outputs/full_data/grasp_no2opt_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/grasp_no2opt_full_alt.csv
```

### Variable Neighborhood Search

```bash
.venv/bin/python vns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 5 \
  --output outputs/benchmark_outputs/full_data/vns_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/vns_full_alt.csv
```

### Large Neighborhood Search

```bash
.venv/bin/python lns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 5 \
  --output outputs/benchmark_outputs/full_data/lns_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/lns_full_alt.csv
```

### Adaptive Large Neighborhood Search

```bash
.venv/bin/python alns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 5 \
  --output outputs/benchmark_outputs/full_data/alns_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/alns_full_alt.csv
```

### Large Neighborhood Search, 120-Second Rerun

```bash
.venv/bin/python lns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 120 \
  --output outputs/benchmark_outputs/full_data/lns_full_120_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/lns_full_120_alt.csv
```

### Adaptive Large Neighborhood Search, 120-Second Rerun

```bash
.venv/bin/python alns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 120 \
  --output outputs/benchmark_outputs/full_data/alns_full_120_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/alns_full_120_alt.csv
```

### Variable Neighborhood Search, 10-Minute Benchmark

```bash
.venv/bin/python vns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 600 \
  --output outputs/benchmark_outputs/full_data_t10/vns_full_t10_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data_t10/vns_full_t10_alt.csv
```

### Large Neighborhood Search, 10-Minute Benchmark

```bash
.venv/bin/python lns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 600 \
  --output outputs/benchmark_outputs/full_data_t10/lns_full_t10_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data_t10/lns_full_t10_alt.csv
```

### Adaptive Large Neighborhood Search, 10-Minute Benchmark

```bash
.venv/bin/python alns_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --time-limit 600 \
  --output outputs/benchmark_outputs/full_data_t10/alns_full_t10_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data_t10/alns_full_t10_alt.csv
```

### GRASP Multi-Start

```bash
.venv/bin/python grasp_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output outputs/benchmark_outputs/full_data/grasp_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/grasp_full_alt.csv
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
  --pick-data-output outputs/benchmark_outputs/full_data/exact_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/exact_full_alt.csv
```

### THM-Min + RR-Style Aisle DP Attempt

```bash
.venv/bin/python thm_min_rr_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output outputs/benchmark_outputs/full_data/thm_rr_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/thm_rr_full_alt.csv
```

This last run did not finish cleanly on the full instance and therefore did not produce benchmarkable output files.

### THM-Min + S-Shape Routing

```bash
.venv/bin/python thm_min_s_shape_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output outputs/benchmark_outputs/full_data/thm_sshape_full_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/full_data/thm_sshape_full_alt.csv
```

This variant has been added to the report for completeness, but it has not yet been benchmarked on the full instance.

## Audit Of Existing Pick-Order File

The file [Grup_Toplama_Verisi_With_PickOrder.csv](../../data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv) was also audited separately.

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

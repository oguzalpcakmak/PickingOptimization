# Route Cleanup Benchmark: 2-opt vs Swap vs Relocate

This report keeps the same allocation/backbone combination fixed and compares only the final route cleanup step.

Base combination: `LK seed for 1-location articles + ascending grouped insertion + open THM shortcut`.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## Old Full Data

- Orders: `data/full/PickOrder.csv`
- Stock: `data/full/StockData.csv`
- Solver stock input: `data/full/StockData.csv`

| Route cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Base time | Cleanup time | Total time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2-opt | 40954.56 | 8059.56 | 6 | 2181 | 2825 | 809 | 205.13s | 0.55s | 205.68s |
| relocate | 41023.80 | 8128.80 | 6 | 2181 | 2825 | 809 | 205.13s | 23.51s | 228.64s |
| swap | 41030.76 | 8135.76 | 6 | 2181 | 2825 | 809 | 205.13s | 9.11s | 214.24s |
| none | 41042.36 | 8147.36 | 6 | 2181 | 2825 | 809 | 205.13s | 0.00s | 205.13s |
| Historical actual operation | 63208.06 | 19483.06 | 6 | 2903 | 6255 | 1649 | n/a | n/a | n/a |

Best cleanup: `2-opt` with objective `40954.56`.
Delta vs no cleanup: `-87.80` objective points.
Delta vs real-operation baseline: `-22253.50` objective points.
Real-operation source: `data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv`.

Artifacts:
- `2-opt` pick output: [two_opt_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/old_full_data/two_opt_pick.csv)
- `2-opt` alternatives: [two_opt_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/old_full_data/two_opt_alt.csv)
- `relocate` pick output: [relocate_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/old_full_data/relocate_pick.csv)
- `relocate` alternatives: [relocate_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/old_full_data/relocate_alt.csv)
- `swap` pick output: [swap_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/old_full_data/swap_pick.csv)
- `swap` alternatives: [swap_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/old_full_data/swap_alt.csv)
- `none` pick output: [none_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/old_full_data/none_pick.csv)
- `none` alternatives: [none_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/old_full_data/none_alt.csv)

## New Data

- Orders: `data/new_data/OrderData.csv`
- Stock: `data/new_data/StockData.csv`
- Solver stock input: `outputs/benchmark_outputs/route_cleanup_comparison/new_data/normalized_stock.csv`

| Route cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Base time | Cleanup time | Total time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | 0.07s | 0.00s | 0.07s |
| 2-opt | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | 0.07s | 0.00s | 0.07s |
| swap | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | 0.07s | 0.00s | 0.07s |
| relocate | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | 0.07s | 0.01s | 0.08s |
| Real pick re-routed baseline | 3514.04 | 1654.04 | 4 | 116 | 196 | 74 | n/a | n/a | n/a |

Best cleanup: `none` with objective `1897.12`.
Delta vs no cleanup: `0.00` objective points.
Delta vs real-operation baseline: `-1616.92` objective points.
Real-operation source: `data/new_data/PickData.csv`.

Artifacts:
- `none` pick output: [none_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/new_data/none_pick.csv)
- `none` alternatives: [none_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/new_data/none_alt.csv)
- `2-opt` pick output: [two_opt_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/new_data/two_opt_pick.csv)
- `2-opt` alternatives: [two_opt_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/new_data/two_opt_alt.csv)
- `swap` pick output: [swap_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/new_data/swap_pick.csv)
- `swap` alternatives: [swap_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/new_data/swap_alt.csv)
- `relocate` pick output: [relocate_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/new_data/relocate_pick.csv)
- `relocate` alternatives: [relocate_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/new_data/relocate_alt.csv)

## 4000 Sample

- Orders: `data/4000_sample/PickOrder_sample_4000.csv`
- Stock: `data/4000_sample/StockData.csv`
- Solver stock input: `data/4000_sample/StockData.csv`

| Route cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Base time | Cleanup time | Total time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2-opt | 32328.44 | 7218.44 | 6 | 1662 | 2077 | 664 | 126.78s | 0.44s | 127.22s |
| relocate | 32411.44 | 7301.44 | 6 | 1662 | 2077 | 664 | 126.78s | 14.00s | 140.78s |
| swap | 32441.40 | 7331.40 | 6 | 1662 | 2077 | 664 | 126.78s | 5.28s | 132.06s |
| none | 32453.00 | 7343.00 | 6 | 1662 | 2077 | 664 | 126.78s | 0.00s | 126.78s |

Best cleanup: `2-opt` with objective `32328.44`.
Delta vs no cleanup: `-124.56` objective points.

Artifacts:
- `2-opt` pick output: [two_opt_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/4000_sample/two_opt_pick.csv)
- `2-opt` alternatives: [two_opt_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/4000_sample/two_opt_alt.csv)
- `relocate` pick output: [relocate_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/4000_sample/relocate_pick.csv)
- `relocate` alternatives: [relocate_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/4000_sample/relocate_alt.csv)
- `swap` pick output: [swap_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/4000_sample/swap_pick.csv)
- `swap` alternatives: [swap_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/4000_sample/swap_alt.csv)
- `none` pick output: [none_pick.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/4000_sample/none_pick.csv)
- `none` alternatives: [none_alt.csv](../../outputs/benchmark_outputs/route_cleanup_comparison/4000_sample/none_alt.csv)

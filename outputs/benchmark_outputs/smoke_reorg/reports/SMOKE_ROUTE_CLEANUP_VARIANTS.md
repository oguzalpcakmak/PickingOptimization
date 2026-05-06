# Route Cleanup Benchmark: 2-opt vs Swap vs Relocate

This report keeps the same allocation/backbone combination fixed and compares only the final route cleanup step.

Base combination: `LK seed for 1-location articles + ascending grouped insertion + open THM shortcut`.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## New Data

- Orders: `data/new_data/OrderData.csv`
- Stock: `data/new_data/StockData.csv`
- Solver stock input: `outputs/benchmark_outputs/smoke_reorg/route_cleanup_variants/new_data/normalized_stock.csv`

| Route cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Base time | Cleanup time | Total time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | 0.07s | 0.00s | 0.07s |
| 2-opt | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | 0.07s | 0.00s | 0.07s |
| swap | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | 0.07s | 0.00s | 0.07s |
| relocate | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | 0.07s | 0.00s | 0.07s |

Best cleanup: `none` with objective `1897.12`.
Delta vs no cleanup: `0.00` objective points.

Artifacts:
- `none` pick output: [none_pick.csv](./outputs/benchmark_outputs/smoke_reorg/route_cleanup_variants/new_data/none_pick.csv)
- `none` alternatives: [none_alt.csv](./outputs/benchmark_outputs/smoke_reorg/route_cleanup_variants/new_data/none_alt.csv)
- `2-opt` pick output: [two_opt_pick.csv](./outputs/benchmark_outputs/smoke_reorg/route_cleanup_variants/new_data/two_opt_pick.csv)
- `2-opt` alternatives: [two_opt_alt.csv](./outputs/benchmark_outputs/smoke_reorg/route_cleanup_variants/new_data/two_opt_alt.csv)
- `swap` pick output: [swap_pick.csv](./outputs/benchmark_outputs/smoke_reorg/route_cleanup_variants/new_data/swap_pick.csv)
- `swap` alternatives: [swap_alt.csv](./outputs/benchmark_outputs/smoke_reorg/route_cleanup_variants/new_data/swap_alt.csv)
- `relocate` pick output: [relocate_pick.csv](./outputs/benchmark_outputs/smoke_reorg/route_cleanup_variants/new_data/relocate_pick.csv)
- `relocate` alternatives: [relocate_alt.csv](./outputs/benchmark_outputs/smoke_reorg/route_cleanup_variants/new_data/relocate_alt.csv)

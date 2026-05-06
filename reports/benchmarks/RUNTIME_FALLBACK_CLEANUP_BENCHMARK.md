# Runtime Cap + Route Cleanup Benchmark

This report starts from the runtime-capped strict insertion + GRASP fallback outputs, then applies final route cleanup variants.

Allocation is fixed within each runtime setting; only the final route order changes between `none`, `2-opt`, `swap`, and `relocate`.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## Old Full Data

- Orders: `PickOrder.csv`
- Stock: `StockData.csv`
- Solver stock input: `StockData.csv`

| Runtime setting | Cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |
|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | 41120.24 | 8135.24 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 0.00s | 123.84s |
| 2 min cap + GRASP fallback | 2-opt | 41026.64 | 8041.64 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 0.58s | 124.42s |
| 2 min cap + GRASP fallback | swap | 41094.52 | 8109.52 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 13.06s | 136.90s |
| 2 min cap + GRASP fallback | relocate | 41068.60 | 8083.60 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 31.39s | 155.23s |
| 5 min cap + GRASP fallback | none | 41032.24 | 8152.24 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 0.00s | 200.83s |
| 5 min cap + GRASP fallback | 2-opt | 40900.92 | 8020.92 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 0.64s | 201.47s |
| 5 min cap + GRASP fallback | swap | 41006.32 | 8126.32 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 10.79s | 211.62s |
| 5 min cap + GRASP fallback | relocate | 40981.76 | 8101.76 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 26.65s | 227.48s |
| Unlimited | none | 41146.44 | 8146.44 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 0.00s | 206.23s |
| Unlimited | 2-opt | 41068.48 | 8068.48 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 0.50s | 206.74s |
| Unlimited | swap | 41120.52 | 8120.52 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 10.91s | 217.14s |
| Unlimited | relocate | 41101.96 | 8101.96 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 26.72s | 232.95s |
| Real pick baseline | recorded CSV + exact-style cross-floor correction | 63208.06 | 19483.06 | 6 | 2903 | 6255 | 1649 | n/a | n/a | n/a | n/a | n/a |

Best objective in this dataset: `5 min cap + GRASP fallback + 2-opt` with `40900.92`.
Delta vs real-operation baseline: `-22307.14` objective points.
Real-operation source: `data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv`.

## New Data

- Orders: `NEW_DATA/OrderData.csv`
- Stock: `NEW_DATA/StockData.csv`
- Solver stock input: `benchmark_outputs/runtime_fallback/new_data/2min/normalized_stock.csv`

| Runtime setting | Cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |
|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | 2-opt | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | swap | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |
| 2 min cap + GRASP fallback | relocate | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.01s | 0.09s |
| 5 min cap + GRASP fallback | none | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.07s |
| 5 min cap + GRASP fallback | 2-opt | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.07s |
| 5 min cap + GRASP fallback | swap | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| 5 min cap + GRASP fallback | relocate | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.01s | 0.08s |
| Unlimited | none | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.07s |
| Unlimited | 2-opt | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| Unlimited | swap | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| Unlimited | relocate | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.01s | 0.08s |
| Real pick baseline | actual selected locations re-routed with shared route builder | 3514.04 | 1654.04 | 4 | 116 | 196 | 74 | n/a | n/a | n/a | n/a | n/a |

Best objective in this dataset: `2 min cap + GRASP fallback + none` with `1897.12`.
Delta vs real-operation baseline: `-1616.92` objective points.
Real-operation source: `data/new_data/PickData.csv`.

## 4000 Sample

- Orders: `4000SAMPLE/PickOrder_sample_4000.csv`
- Stock: `4000SAMPLE/StockData.csv`
- Solver stock input: `4000SAMPLE/StockData.csv`

| Runtime setting | Cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |
|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | 32571.60 | 7371.60 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 0.00s | 121.07s |
| 2 min cap + GRASP fallback | 2-opt | 32434.04 | 7234.04 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 0.46s | 121.53s |
| 2 min cap + GRASP fallback | swap | 32558.44 | 7358.44 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 6.75s | 127.82s |
| 2 min cap + GRASP fallback | relocate | 32498.52 | 7298.52 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 17.01s | 138.08s |
| 5 min cap + GRASP fallback | none | 32404.72 | 7309.72 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 0.00s | 129.85s |
| 5 min cap + GRASP fallback | 2-opt | 32329.48 | 7234.48 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 0.32s | 130.17s |
| 5 min cap + GRASP fallback | swap | 32393.12 | 7298.12 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 5.50s | 135.35s |
| 5 min cap + GRASP fallback | relocate | 32381.72 | 7286.72 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 14.95s | 144.79s |
| Unlimited | none | 32566.28 | 7351.28 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 0.00s | 132.14s |
| Unlimited | 2-opt | 32495.48 | 7280.48 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 0.33s | 132.47s |
| Unlimited | swap | 32560.48 | 7345.48 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 5.72s | 137.87s |
| Unlimited | relocate | 32532.08 | 7317.08 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 17.14s | 149.28s |

Best objective in this dataset: `5 min cap + GRASP fallback + 2-opt` with `32329.48`.

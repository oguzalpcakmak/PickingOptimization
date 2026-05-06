# First vs Best Improvement Cleanup Benchmark

This report compares first-improvement and best-improvement local search on top of the runtime fallback benchmark outputs.

Allocation is fixed within each runtime setting. Only the final route cleanup strategy changes.

Definition used here: first improvement applies the first improving move found in scan order; best improvement scans the full neighborhood and applies the best improving move.

Both strategies are limited to `3` accepted moves/passes per floor to match the previous cleanup benchmark scale.

Note: this is a pure first-vs-best comparison. The earlier cleanup benchmark used a greedy pass that updated the route immediately while continuing the scan, so its numbers are not expected to match this table exactly.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## Old Full Data

- Orders: `PickOrder.csv`
- Stock: `StockData.csv`
- Solver stock input: `StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | first improvement | 41120.24 | 8135.24 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 0.00s | 123.84s |
| 2 min cap + GRASP fallback | none | best improvement | 41120.24 | 8135.24 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 0.00s | 123.84s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 41052.96 | 8067.96 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 0.42s | 124.26s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 41048.08 | 8063.08 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 0.67s | 124.52s |
| 2 min cap + GRASP fallback | swap | first improvement | 41094.52 | 8109.52 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 0.99s | 124.83s |
| 2 min cap + GRASP fallback | swap | best improvement | 41094.52 | 8109.52 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 1.07s | 124.91s |
| 2 min cap + GRASP fallback | relocate | first improvement | 41068.60 | 8083.60 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 1.39s | 125.23s |
| 2 min cap + GRASP fallback | relocate | best improvement | 41068.60 | 8083.60 | 6 | 2187 | 2822 | 820 | Yes | 833 | 123.84s | 1.70s | 125.54s |
| 5 min cap + GRASP fallback | none | first improvement | 41032.24 | 8152.24 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 0.00s | 200.83s |
| 5 min cap + GRASP fallback | none | best improvement | 41032.24 | 8152.24 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 0.00s | 200.83s |
| 5 min cap + GRASP fallback | 2-opt | first improvement | 40934.40 | 8054.40 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 0.40s | 201.24s |
| 5 min cap + GRASP fallback | 2-opt | best improvement | 40929.52 | 8049.52 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 0.69s | 201.52s |
| 5 min cap + GRASP fallback | swap | first improvement | 41006.32 | 8126.32 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 0.72s | 201.55s |
| 5 min cap + GRASP fallback | swap | best improvement | 41006.32 | 8126.32 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 0.77s | 201.61s |
| 5 min cap + GRASP fallback | relocate | first improvement | 40981.76 | 8101.76 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 1.22s | 202.06s |
| 5 min cap + GRASP fallback | relocate | best improvement | 40981.76 | 8101.76 | 6 | 2180 | 2821 | 802 | No | 0 | 200.83s | 1.51s | 202.34s |
| Unlimited | none | first improvement | 41146.44 | 8146.44 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 0.00s | 206.23s |
| Unlimited | none | best improvement | 41146.44 | 8146.44 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 0.00s | 206.23s |
| Unlimited | 2-opt | first improvement | 41068.28 | 8068.28 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 0.49s | 206.73s |
| Unlimited | 2-opt | best improvement | 41068.48 | 8068.48 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 0.61s | 206.84s |
| Unlimited | swap | first improvement | 41120.52 | 8120.52 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 0.71s | 206.94s |
| Unlimited | swap | best improvement | 41120.52 | 8120.52 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 0.80s | 207.03s |
| Unlimited | relocate | first improvement | 41101.96 | 8101.96 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 1.28s | 207.51s |
| Unlimited | relocate | best improvement | 41101.96 | 8101.96 | 6 | 2188 | 2824 | 804 | No | 0 | 206.23s | 1.55s | 207.78s |
| Real pick baseline | real operation | recorded CSV + exact-style cross-floor correction | 63208.06 | 19483.06 | 6 | 2903 | 6255 | 1649 | n/a | n/a | n/a | n/a | n/a |

Best objective in this dataset: `5 min cap + GRASP fallback + 2-opt + best improvement` with `40929.52`.
Delta vs real-operation baseline: `-22278.54` objective points.
Real-operation source: `data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv`.

## New Data

- Orders: `NEW_DATA/OrderData.csv`
- Stock: `NEW_DATA/StockData.csv`
- Solver stock input: `benchmark_outputs/runtime_fallback/new_data/2min/normalized_stock.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | none | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.08s |
| 2 min cap + GRASP fallback | swap | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |
| 2 min cap + GRASP fallback | swap | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |
| 2 min cap + GRASP fallback | relocate | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |
| 2 min cap + GRASP fallback | relocate | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.08s | 0.00s | 0.09s |
| 5 min cap + GRASP fallback | none | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.07s |
| 5 min cap + GRASP fallback | none | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.07s |
| 5 min cap + GRASP fallback | 2-opt | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.07s |
| 5 min cap + GRASP fallback | 2-opt | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.07s |
| 5 min cap + GRASP fallback | swap | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| 5 min cap + GRASP fallback | swap | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| 5 min cap + GRASP fallback | relocate | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| 5 min cap + GRASP fallback | relocate | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| Unlimited | none | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.07s |
| Unlimited | none | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.07s |
| Unlimited | 2-opt | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| Unlimited | 2-opt | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| Unlimited | swap | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| Unlimited | swap | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| Unlimited | relocate | first improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| Unlimited | relocate | best improvement | 1897.12 | 967.12 | 4 | 54 | 80 | 33 | No | 0 | 0.07s | 0.00s | 0.08s |
| Real pick baseline | real operation | actual selected locations re-routed with shared route builder | 3514.04 | 1654.04 | 4 | 116 | 196 | 74 | n/a | n/a | n/a | n/a | n/a |

Best objective in this dataset: `2 min cap + GRASP fallback + none + first improvement` with `1897.12`.
Delta vs real-operation baseline: `-1616.92` objective points.
Real-operation source: `data/new_data/PickData.csv`.

## 4000 Sample

- Orders: `4000SAMPLE/PickOrder_sample_4000.csv`
- Stock: `4000SAMPLE/StockData.csv`
- Solver stock input: `4000SAMPLE/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | first improvement | 32571.60 | 7371.60 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 0.00s | 121.07s |
| 2 min cap + GRASP fallback | none | best improvement | 32571.60 | 7371.60 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 0.00s | 121.07s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 32484.92 | 7284.92 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 0.29s | 121.36s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 32458.40 | 7258.40 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 0.54s | 121.61s |
| 2 min cap + GRASP fallback | swap | first improvement | 32558.44 | 7358.44 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 0.64s | 121.72s |
| 2 min cap + GRASP fallback | swap | best improvement | 32547.04 | 7347.04 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 0.64s | 121.72s |
| 2 min cap + GRASP fallback | relocate | first improvement | 32509.92 | 7309.92 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 0.91s | 121.99s |
| 2 min cap + GRASP fallback | relocate | best improvement | 32498.52 | 7298.52 | 6 | 1668 | 2077 | 671 | Yes | 56 | 121.07s | 1.33s | 122.40s |
| 5 min cap + GRASP fallback | none | first improvement | 32404.72 | 7309.72 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 0.00s | 129.85s |
| 5 min cap + GRASP fallback | none | best improvement | 32404.72 | 7309.72 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 0.00s | 129.85s |
| 5 min cap + GRASP fallback | 2-opt | first improvement | 32361.20 | 7266.20 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 0.24s | 130.09s |
| 5 min cap + GRASP fallback | 2-opt | best improvement | 32346.68 | 7251.68 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 0.32s | 130.16s |
| 5 min cap + GRASP fallback | swap | first improvement | 32393.12 | 7298.12 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 0.44s | 130.29s |
| 5 min cap + GRASP fallback | swap | best improvement | 32393.12 | 7298.12 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 0.60s | 130.45s |
| 5 min cap + GRASP fallback | relocate | first improvement | 32381.72 | 7286.72 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 0.92s | 130.76s |
| 5 min cap + GRASP fallback | relocate | best improvement | 32381.72 | 7286.72 | 6 | 1661 | 2076 | 671 | No | 0 | 129.85s | 1.10s | 130.95s |
| Unlimited | none | first improvement | 32566.28 | 7351.28 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 0.00s | 132.15s |
| Unlimited | none | best improvement | 32566.28 | 7351.28 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 0.00s | 132.14s |
| Unlimited | 2-opt | first improvement | 32507.28 | 7292.28 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 0.24s | 132.39s |
| Unlimited | 2-opt | best improvement | 32501.08 | 7286.08 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 0.40s | 132.55s |
| Unlimited | swap | first improvement | 32560.48 | 7345.48 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 0.47s | 132.62s |
| Unlimited | swap | best improvement | 32560.48 | 7345.48 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 0.48s | 132.62s |
| Unlimited | relocate | first improvement | 32532.08 | 7317.08 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 0.87s | 133.01s |
| Unlimited | relocate | best improvement | 32532.08 | 7317.08 | 6 | 1669 | 2076 | 671 | No | 0 | 132.14s | 1.12s | 133.26s |

Best objective in this dataset: `5 min cap + GRASP fallback + 2-opt + best improvement` with `32346.68`.

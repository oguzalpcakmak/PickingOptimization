# C++ Current-Best Comprehensive Benchmark

This report benchmarks the C++ current-best solver across runtime budgets, cleanup operators, and first/best improvement strategies.

Pipeline: `one-location prep + pure C++ seed route + ascending grouped strict insertion + open THM shortcut + grasp fallback + delta-cost cleanup`.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## Old Full Data

- Orders: `data/full/PickOrder.csv`
- Stock: `data/full/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cleanup locations | Cleanup passes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | first improvement | 41248.84 | 8233.84 | 6 | 2189 | 2830 | 819 | 819 | 0/1 | No | 0 | 17551 | 1684508 | 0.8220s | 0.0005s | 0.8226s |
| 2 min cap + GRASP fallback | none | best improvement | 41248.84 | 8233.84 | 6 | 2189 | 2830 | 819 | 819 | 0/1 | No | 0 | 17551 | 1684508 | 0.7996s | 0.0006s | 0.8002s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 41131.40 | 8116.40 | 6 | 2189 | 2830 | 819 | 819 | 14/3 | No | 0 | 17551 | 1684508 | 0.7985s | 0.0028s | 0.8013s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 41125.60 | 8110.60 | 6 | 2189 | 2830 | 819 | 819 | 14/3 | No | 0 | 17551 | 1684508 | 0.7983s | 0.0040s | 0.8023s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 41099.48 | 8084.48 | 6 | 2189 | 2830 | 819 | 819 | 18/1000000 | No | 0 | 17551 | 1684508 | 0.7950s | 0.0043s | 0.7993s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 41099.48 | 8084.48 | 6 | 2189 | 2830 | 819 | 819 | 17/1000000 | No | 0 | 17551 | 1684508 | 0.7987s | 0.0052s | 0.8038s |
| 2 min cap + GRASP fallback | swap | first improvement | 41218.28 | 8203.28 | 6 | 2189 | 2830 | 819 | 819 | 5/3 | No | 0 | 17551 | 1684508 | 0.7971s | 0.0194s | 0.8165s |
| 2 min cap + GRASP fallback | swap | best improvement | 41218.28 | 8203.28 | 6 | 2189 | 2830 | 819 | 819 | 5/3 | No | 0 | 17551 | 1684508 | 0.7980s | 0.0241s | 0.8221s |
| 2 min cap + GRASP fallback | relocate | first improvement | 41207.28 | 8192.28 | 6 | 2189 | 2830 | 819 | 819 | 6/3 | No | 0 | 17551 | 1684508 | 0.7978s | 0.0158s | 0.8136s |
| 2 min cap + GRASP fallback | relocate | best improvement | 41207.28 | 8192.28 | 6 | 2189 | 2830 | 819 | 819 | 6/3 | No | 0 | 17551 | 1684508 | 0.7973s | 0.0218s | 0.8191s |
| Real pick baseline | real operation | recorded CSV + exact-style cross-floor correction | 63208.06 | 19483.06 | 6 | 2903 | 6255 | 1649 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective: `2 min cap + GRASP fallback + 2-opt + first improvement` with `41099.48`.
Fastest run: `2 min cap + GRASP fallback + 2-opt + first improvement` in `0.7993s`.
Delta vs real-operation baseline: `-22108.58` objective points.
Real-operation source: `data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv`.

## New Data

- Orders: `data/new_data/OrderData.csv`
- Stock: `data/new_data/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cleanup locations | Cleanup passes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 0/1 | No | 0 | 419 | 3303 | 0.0035s | 0.0000s | 0.0035s |
| 2 min cap + GRASP fallback | none | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 0/1 | No | 0 | 419 | 3303 | 0.0027s | 0.0000s | 0.0027s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 0/3 | No | 0 | 419 | 3303 | 0.0026s | 0.0000s | 0.0026s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 0/3 | No | 0 | 419 | 3303 | 0.0026s | 0.0000s | 0.0027s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 0/1000000 | No | 0 | 419 | 3303 | 0.0026s | 0.0000s | 0.0026s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 0/1000000 | No | 0 | 419 | 3303 | 0.0075s | 0.0000s | 0.0076s |
| 2 min cap + GRASP fallback | swap | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 1/3 | No | 0 | 419 | 3303 | 0.0030s | 0.0001s | 0.0030s |
| 2 min cap + GRASP fallback | swap | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 1/3 | No | 0 | 419 | 3303 | 0.0028s | 0.0001s | 0.0028s |
| 2 min cap + GRASP fallback | relocate | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 0/3 | No | 0 | 419 | 3303 | 0.0027s | 0.0000s | 0.0027s |
| 2 min cap + GRASP fallback | relocate | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | 35 | 0/3 | No | 0 | 419 | 3303 | 0.0028s | 0.0000s | 0.0029s |
| Real pick baseline | real operation | actual selected locations re-routed with shared route builder | 3514.04 | 1654.04 | 4 | 116 | 196 | 74 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective: `2 min cap + GRASP fallback + none + first improvement` with `1881.92`.
Fastest run: `2 min cap + GRASP fallback + 2-opt + first improvement` in `0.0026s`.
Delta vs real-operation baseline: `-1632.12` objective points.
Real-operation source: `data/new_data/PickData.csv`.

## 4000 Sample

- Orders: `data/4000_sample/PickOrder_sample_4000.csv`
- Stock: `data/4000_sample/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cleanup locations | Cleanup passes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + GRASP fallback | none | first improvement | 32523.88 | 7323.88 | 6 | 1668 | 2077 | 660 | 660 | 0/1 | No | 0 | 14170 | 1229554 | 0.5278s | 0.0004s | 0.5282s |
| 2 min cap + GRASP fallback | none | best improvement | 32523.88 | 7323.88 | 6 | 1668 | 2077 | 660 | 660 | 0/1 | No | 0 | 14170 | 1229554 | 0.5238s | 0.0004s | 0.5242s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 32416.72 | 7216.72 | 6 | 1668 | 2077 | 660 | 660 | 9/3 | No | 0 | 14170 | 1229554 | 0.5285s | 0.0017s | 0.5302s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 32416.72 | 7216.72 | 6 | 1668 | 2077 | 660 | 660 | 9/3 | No | 0 | 14170 | 1229554 | 0.5266s | 0.0023s | 0.5290s |
| 2 min cap + GRASP fallback | 2-opt | first improvement | 32393.52 | 7193.52 | 6 | 1668 | 2077 | 660 | 660 | 13/1000000 | No | 0 | 14170 | 1229554 | 0.5254s | 0.0026s | 0.5280s |
| 2 min cap + GRASP fallback | 2-opt | best improvement | 32393.52 | 7193.52 | 6 | 1668 | 2077 | 660 | 660 | 13/1000000 | No | 0 | 14170 | 1229554 | 0.5272s | 0.0034s | 0.5307s |
| 2 min cap + GRASP fallback | swap | first improvement | 32527.00 | 7327.00 | 6 | 1668 | 2077 | 660 | 660 | 5/3 | No | 0 | 14170 | 1229554 | 0.5267s | 0.0112s | 0.5379s |
| 2 min cap + GRASP fallback | swap | best improvement | 32527.00 | 7327.00 | 6 | 1668 | 2077 | 660 | 660 | 5/3 | No | 0 | 14170 | 1229554 | 0.5258s | 0.0157s | 0.5415s |
| 2 min cap + GRASP fallback | relocate | first improvement | 32495.28 | 7295.28 | 6 | 1668 | 2077 | 660 | 660 | 4/3 | No | 0 | 14170 | 1229554 | 0.5252s | 0.0087s | 0.5339s |
| 2 min cap + GRASP fallback | relocate | best improvement | 32495.28 | 7295.28 | 6 | 1668 | 2077 | 660 | 660 | 3/3 | No | 0 | 14170 | 1229554 | 0.5267s | 0.0104s | 0.5371s |

Best objective: `2 min cap + GRASP fallback + 2-opt + first improvement` with `32393.52`.
Fastest run: `2 min cap + GRASP fallback + none + best improvement` in `0.5242s`.

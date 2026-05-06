# Python V2 Flow Comprehensive Benchmark

This report benchmarks the Python v2 flow across datasets, runtime budgets, cleanup operators, and first/best improvement strategies.

V2 construction pipeline: `one-location LK seed + ascending grouped strict insertion + visited-area fallback on timeout`.

Fairness note: the v2 solver has a fixed built-in final cleanup sequence. This runner temporarily disables that built-in cleanup, then applies each cleanup variant from the same v2 allocation.

Cleanup variants include the single operators plus the v2 sequence `2-opt -> swap -> relocate`.

Cleanup pass limit: `3` per floor/operator.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## Old Full Data

- Orders: `data/full/PickOrder.csv`
- Stock: `data/full/StockData.csv`
- Solver stock input: `data/full/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + visited-area fallback | none | first improvement | 42508.00 | 8368.00 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 0.0007s | 120.4926s |
| 2 min cap + visited-area fallback | none | best improvement | 42508.00 | 8368.00 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 0.0007s | 120.4926s |
| 2 min cap + visited-area fallback | 2-opt | first improvement | 42418.24 | 8278.24 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 0.5163s | 121.0082s |
| 2 min cap + visited-area fallback | 2-opt | best improvement | 42418.44 | 8278.44 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 0.6820s | 121.1739s |
| 2 min cap + visited-area fallback | swap | first improvement | 42482.08 | 8342.08 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 0.7323s | 121.2242s |
| 2 min cap + visited-area fallback | swap | best improvement | 42482.08 | 8342.08 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 0.8318s | 121.3237s |
| 2 min cap + visited-area fallback | relocate | first improvement | 42451.92 | 8311.92 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 1.4034s | 121.8953s |
| 2 min cap + visited-area fallback | relocate | best improvement | 42451.92 | 8311.92 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 1.7623s | 122.2542s |
| 2 min cap + visited-area fallback | 2-opt -> swap -> relocate | first improvement | 42405.28 | 8265.28 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 2.2376s | 122.7295s |
| 2 min cap + visited-area fallback | 2-opt -> swap -> relocate | best improvement | 42405.48 | 8265.48 | 6 | 2264 | 2860 | 823 | Yes | 1185 | 12810 | 1055537 | 120.4919s | 2.5096s | 123.0014s |
| 5 min cap + visited-area fallback | none | first improvement | 41471.04 | 8156.04 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 0.0008s | 275.8996s |
| 5 min cap + visited-area fallback | none | best improvement | 41471.04 | 8156.04 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 0.0007s | 275.8995s |
| 5 min cap + visited-area fallback | 2-opt | first improvement | 41395.08 | 8080.08 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 0.4870s | 276.3858s |
| 5 min cap + visited-area fallback | 2-opt | best improvement | 41389.48 | 8074.48 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 0.6238s | 276.5226s |
| 5 min cap + visited-area fallback | swap | first improvement | 41453.64 | 8138.64 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 0.7575s | 276.6563s |
| 5 min cap + visited-area fallback | swap | best improvement | 41453.64 | 8138.64 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 0.7745s | 276.6733s |
| 5 min cap + visited-area fallback | relocate | first improvement | 41412.48 | 8097.48 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 1.3717s | 277.2705s |
| 5 min cap + visited-area fallback | relocate | best improvement | 41412.48 | 8097.48 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 1.8904s | 277.7892s |
| 5 min cap + visited-area fallback | 2-opt -> swap -> relocate | first improvement | 41387.92 | 8072.92 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 1.9289s | 277.8277s |
| 5 min cap + visited-area fallback | 2-opt -> swap -> relocate | best improvement | 41388.12 | 8073.12 | 6 | 2209 | 2845 | 789 | No | 0 | 25622 | 2347190 | 275.8988s | 1.9981s | 277.8969s |
| Real pick baseline | real operation | recorded CSV + exact-style cross-floor correction | 63208.06 | 19483.06 | 6 | 2903 | 6255 | 1649 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective: `5 min cap + visited-area fallback + 2-opt -> swap -> relocate + first improvement` with `41387.92`.
Fastest run: `2 min cap + visited-area fallback + none + first improvement` in `120.4926s`.
Delta vs real-operation baseline: `-21820.14` objective points.
Real-operation source: `data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv`.

## New Data

- Orders: `data/new_data/OrderData.csv`
- Stock: `data/new_data/StockData.csv`
- Solver stock input: `outputs/benchmark_outputs/python_v2_combinations/new_data/2min/_base/normalized_stock.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + visited-area fallback | none | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0001s | 0.1482s |
| 2 min cap + visited-area fallback | none | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0001s | 0.1482s |
| 2 min cap + visited-area fallback | 2-opt | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0012s | 0.1493s |
| 2 min cap + visited-area fallback | 2-opt | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0011s | 0.1492s |
| 2 min cap + visited-area fallback | swap | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0021s | 0.1502s |
| 2 min cap + visited-area fallback | swap | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0022s | 0.1503s |
| 2 min cap + visited-area fallback | relocate | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0029s | 0.1510s |
| 2 min cap + visited-area fallback | relocate | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0028s | 0.1509s |
| 2 min cap + visited-area fallback | 2-opt -> swap -> relocate | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0056s | 0.1537s |
| 2 min cap + visited-area fallback | 2-opt -> swap -> relocate | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1481s | 0.0057s | 0.1539s |
| 5 min cap + visited-area fallback | none | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0001s | 0.1513s |
| 5 min cap + visited-area fallback | none | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0001s | 0.1513s |
| 5 min cap + visited-area fallback | 2-opt | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0011s | 0.1524s |
| 5 min cap + visited-area fallback | 2-opt | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0011s | 0.1524s |
| 5 min cap + visited-area fallback | swap | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0019s | 0.1532s |
| 5 min cap + visited-area fallback | swap | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0019s | 0.1531s |
| 5 min cap + visited-area fallback | relocate | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0028s | 0.1540s |
| 5 min cap + visited-area fallback | relocate | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0030s | 0.1542s |
| 5 min cap + visited-area fallback | 2-opt -> swap -> relocate | first improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0060s | 0.1573s |
| 5 min cap + visited-area fallback | 2-opt -> swap -> relocate | best improvement | 1917.72 | 972.72 | 4 | 55 | 81 | 33 | No | 0 | 889 | 7761 | 0.1513s | 0.0059s | 0.1572s |
| Real pick baseline | real operation | actual selected locations re-routed with shared route builder | 3514.04 | 1654.04 | 4 | 116 | 196 | 74 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective: `2 min cap + visited-area fallback + none + first improvement` with `1917.72`.
Fastest run: `2 min cap + visited-area fallback + none + best improvement` in `0.1482s`.
Delta vs real-operation baseline: `-1596.32` objective points.
Real-operation source: `data/new_data/PickData.csv`.

## 4000 Sample

- Orders: `data/4000_sample/PickOrder_sample_4000.csv`
- Stock: `data/4000_sample/StockData.csv`
- Solver stock input: `data/4000_sample/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + visited-area fallback | none | first improvement | 32661.36 | 7296.36 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 0.0006s | 120.1798s |
| 2 min cap + visited-area fallback | none | best improvement | 32661.36 | 7296.36 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 0.0006s | 120.1798s |
| 2 min cap + visited-area fallback | 2-opt | first improvement | 32618.24 | 7253.24 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 0.2464s | 120.4256s |
| 2 min cap + visited-area fallback | 2-opt | best improvement | 32613.80 | 7248.80 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 0.3373s | 120.5165s |
| 2 min cap + visited-area fallback | swap | first improvement | 32649.76 | 7284.76 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 0.5158s | 120.6949s |
| 2 min cap + visited-area fallback | swap | best improvement | 32649.76 | 7284.76 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 0.5206s | 120.6998s |
| 2 min cap + visited-area fallback | relocate | first improvement | 32638.56 | 7273.56 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 0.6623s | 120.8415s |
| 2 min cap + visited-area fallback | relocate | best improvement | 32638.56 | 7273.56 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 0.8188s | 120.9980s |
| 2 min cap + visited-area fallback | 2-opt -> swap -> relocate | first improvement | 32606.64 | 7241.64 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 1.2703s | 121.4494s |
| 2 min cap + visited-area fallback | 2-opt -> swap -> relocate | best improvement | 32596.60 | 7231.60 | 6 | 1679 | 2089 | 657 | Yes | 215 | 15206 | 1221690 | 120.1792s | 1.5001s | 121.6793s |
| 5 min cap + visited-area fallback | none | first improvement | 32636.60 | 7346.60 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 0.0006s | 162.7214s |
| 5 min cap + visited-area fallback | none | best improvement | 32636.60 | 7346.60 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 0.0006s | 162.7214s |
| 5 min cap + visited-area fallback | 2-opt | first improvement | 32564.04 | 7274.04 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 0.3102s | 163.0310s |
| 5 min cap + visited-area fallback | 2-opt | best improvement | 32562.48 | 7272.48 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 0.4236s | 163.1444s |
| 5 min cap + visited-area fallback | swap | first improvement | 32625.00 | 7335.00 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 0.4077s | 163.1285s |
| 5 min cap + visited-area fallback | swap | best improvement | 32625.00 | 7335.00 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 0.4421s | 163.1629s |
| 5 min cap + visited-area fallback | relocate | first improvement | 32608.00 | 7318.00 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 0.7066s | 163.4274s |
| 5 min cap + visited-area fallback | relocate | best improvement | 32608.00 | 7318.00 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 0.9129s | 163.6337s |
| 5 min cap + visited-area fallback | 2-opt -> swap -> relocate | first improvement | 32546.64 | 7256.64 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 1.2483s | 163.9691s |
| 5 min cap + visited-area fallback | 2-opt -> swap -> relocate | best improvement | 32545.08 | 7255.08 | 6 | 1674 | 2085 | 650 | No | 0 | 19468 | 1637736 | 162.7208s | 1.4320s | 164.1528s |

Best objective: `5 min cap + visited-area fallback + 2-opt -> swap -> relocate + best improvement` with `32545.08`.
Fastest run: `2 min cap + visited-area fallback + none + first improvement` in `120.1798s`.

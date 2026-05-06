# C++ Current-Best Comprehensive Benchmark

This report benchmarks the C++ current-best solver across runtime budgets, cleanup operators, and first/best improvement strategies.

Pipeline: `one-location prep + pure C++ seed route + ascending grouped strict insertion + open THM shortcut + visited-area fallback + delta-cost cleanup`.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## Old Full Data

- Orders: `data/full/PickOrder.csv`
- Stock: `data/full/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + visited-area fallback | none | first improvement | 41248.84 | 8233.84 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8224s | 0.0005s | 0.8229s |
| 2 min cap + visited-area fallback | none | best improvement | 41248.84 | 8233.84 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8254s | 0.0005s | 0.8259s |
| 2 min cap + visited-area fallback | 2-opt | first improvement | 41131.40 | 8116.40 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8227s | 0.0029s | 0.8256s |
| 2 min cap + visited-area fallback | 2-opt | best improvement | 41125.60 | 8110.60 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8711s | 0.0039s | 0.8750s |
| 2 min cap + visited-area fallback | swap | first improvement | 41218.28 | 8203.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8139s | 0.0193s | 0.8332s |
| 2 min cap + visited-area fallback | swap | best improvement | 41218.28 | 8203.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8236s | 0.0241s | 0.8478s |
| 2 min cap + visited-area fallback | relocate | first improvement | 41207.28 | 8192.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8235s | 0.0166s | 0.8400s |
| 2 min cap + visited-area fallback | relocate | best improvement | 41207.28 | 8192.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8265s | 0.0234s | 0.8499s |
| 5 min cap + visited-area fallback | none | first improvement | 41248.84 | 8233.84 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8205s | 0.0005s | 0.8211s |
| 5 min cap + visited-area fallback | none | best improvement | 41248.84 | 8233.84 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8222s | 0.0006s | 0.8228s |
| 5 min cap + visited-area fallback | 2-opt | first improvement | 41131.40 | 8116.40 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8252s | 0.0029s | 0.8281s |
| 5 min cap + visited-area fallback | 2-opt | best improvement | 41125.60 | 8110.60 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8175s | 0.0041s | 0.8216s |
| 5 min cap + visited-area fallback | swap | first improvement | 41218.28 | 8203.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8215s | 0.0193s | 0.8408s |
| 5 min cap + visited-area fallback | swap | best improvement | 41218.28 | 8203.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8212s | 0.0239s | 0.8451s |
| 5 min cap + visited-area fallback | relocate | first improvement | 41207.28 | 8192.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8572s | 0.0163s | 0.8735s |
| 5 min cap + visited-area fallback | relocate | best improvement | 41207.28 | 8192.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8203s | 0.0224s | 0.8428s |
| Unlimited | none | first improvement | 41248.84 | 8233.84 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8175s | 0.0005s | 0.8180s |
| Unlimited | none | best improvement | 41248.84 | 8233.84 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8219s | 0.0005s | 0.8224s |
| Unlimited | 2-opt | first improvement | 41131.40 | 8116.40 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8217s | 0.0030s | 0.8247s |
| Unlimited | 2-opt | best improvement | 41125.60 | 8110.60 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8225s | 0.0039s | 0.8264s |
| Unlimited | swap | first improvement | 41218.28 | 8203.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8229s | 0.0193s | 0.8423s |
| Unlimited | swap | best improvement | 41218.28 | 8203.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8139s | 0.0238s | 0.8377s |
| Unlimited | relocate | first improvement | 41207.28 | 8192.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8602s | 0.0161s | 0.8763s |
| Unlimited | relocate | best improvement | 41207.28 | 8192.28 | 6 | 2189 | 2830 | 819 | No | 0 | 17551 | 1684508 | 0.8156s | 0.0227s | 0.8383s |
| Real pick baseline | real operation | recorded CSV + exact-style cross-floor correction | 63208.06 | 19483.06 | 6 | 2903 | 6255 | 1649 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective: `2 min cap + visited-area fallback + 2-opt + best improvement` with `41125.60`.
Fastest run: `Unlimited + none + first improvement` in `0.8180s`.
Delta vs real-operation baseline: `-22082.46` objective points.
Real-operation source: `data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv`.

## New Data

- Orders: `data/new_data/OrderData.csv`
- Stock: `data/new_data/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + visited-area fallback | none | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0038s | 0.0000s | 0.0038s |
| 2 min cap + visited-area fallback | none | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0027s | 0.0000s | 0.0027s |
| 2 min cap + visited-area fallback | 2-opt | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0034s | 0.0000s | 0.0034s |
| 2 min cap + visited-area fallback | 2-opt | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0029s | 0.0000s | 0.0029s |
| 2 min cap + visited-area fallback | swap | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0028s | 0.0000s | 0.0028s |
| 2 min cap + visited-area fallback | swap | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0029s | 0.0001s | 0.0029s |
| 2 min cap + visited-area fallback | relocate | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0029s | 0.0000s | 0.0029s |
| 2 min cap + visited-area fallback | relocate | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0027s | 0.0000s | 0.0027s |
| 5 min cap + visited-area fallback | none | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0030s | 0.0000s | 0.0030s |
| 5 min cap + visited-area fallback | none | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0033s | 0.0000s | 0.0034s |
| 5 min cap + visited-area fallback | 2-opt | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0028s | 0.0000s | 0.0028s |
| 5 min cap + visited-area fallback | 2-opt | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0028s | 0.0000s | 0.0029s |
| 5 min cap + visited-area fallback | swap | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0028s | 0.0001s | 0.0028s |
| 5 min cap + visited-area fallback | swap | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0027s | 0.0001s | 0.0028s |
| 5 min cap + visited-area fallback | relocate | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0028s | 0.0001s | 0.0029s |
| 5 min cap + visited-area fallback | relocate | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0029s | 0.0000s | 0.0030s |
| Unlimited | none | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0029s | 0.0000s | 0.0029s |
| Unlimited | none | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0028s | 0.0000s | 0.0028s |
| Unlimited | 2-opt | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0028s | 0.0000s | 0.0028s |
| Unlimited | 2-opt | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0028s | 0.0000s | 0.0028s |
| Unlimited | swap | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0027s | 0.0001s | 0.0027s |
| Unlimited | swap | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0027s | 0.0001s | 0.0028s |
| Unlimited | relocate | first improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0030s | 0.0000s | 0.0031s |
| Unlimited | relocate | best improvement | 1881.92 | 966.92 | 4 | 53 | 80 | 35 | No | 0 | 419 | 3303 | 0.0029s | 0.0000s | 0.0030s |
| Real pick baseline | real operation | actual selected locations re-routed with shared route builder | 3514.04 | 1654.04 | 4 | 116 | 196 | 74 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective: `2 min cap + visited-area fallback + none + first improvement` with `1881.92`.
Fastest run: `2 min cap + visited-area fallback + none + best improvement` in `0.0027s`.
Delta vs real-operation baseline: `-1632.12` objective points.
Real-operation source: `data/new_data/PickData.csv`.

## 4000 Sample

- Orders: `data/4000_sample/PickOrder_sample_4000.csv`
- Stock: `data/4000_sample/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + visited-area fallback | none | first improvement | 32523.88 | 7323.88 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5560s | 0.0004s | 0.5564s |
| 2 min cap + visited-area fallback | none | best improvement | 32523.88 | 7323.88 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5457s | 0.0004s | 0.5461s |
| 2 min cap + visited-area fallback | 2-opt | first improvement | 32416.72 | 7216.72 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5416s | 0.0017s | 0.5433s |
| 2 min cap + visited-area fallback | 2-opt | best improvement | 32416.72 | 7216.72 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5434s | 0.0025s | 0.5460s |
| 2 min cap + visited-area fallback | swap | first improvement | 32527.00 | 7327.00 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5423s | 0.0112s | 0.5535s |
| 2 min cap + visited-area fallback | swap | best improvement | 32527.00 | 7327.00 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5850s | 0.0153s | 0.6003s |
| 2 min cap + visited-area fallback | relocate | first improvement | 32495.28 | 7295.28 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5458s | 0.0091s | 0.5549s |
| 2 min cap + visited-area fallback | relocate | best improvement | 32495.28 | 7295.28 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5469s | 0.0109s | 0.5578s |
| 5 min cap + visited-area fallback | none | first improvement | 32523.88 | 7323.88 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5443s | 0.0004s | 0.5447s |
| 5 min cap + visited-area fallback | none | best improvement | 32523.88 | 7323.88 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5423s | 0.0004s | 0.5427s |
| 5 min cap + visited-area fallback | 2-opt | first improvement | 32416.72 | 7216.72 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5380s | 0.0017s | 0.5398s |
| 5 min cap + visited-area fallback | 2-opt | best improvement | 32416.72 | 7216.72 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5411s | 0.0025s | 0.5436s |
| 5 min cap + visited-area fallback | swap | first improvement | 32527.00 | 7327.00 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5370s | 0.0112s | 0.5482s |
| 5 min cap + visited-area fallback | swap | best improvement | 32527.00 | 7327.00 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5426s | 0.0156s | 0.5582s |
| 5 min cap + visited-area fallback | relocate | first improvement | 32495.28 | 7295.28 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5782s | 0.0090s | 0.5873s |
| 5 min cap + visited-area fallback | relocate | best improvement | 32495.28 | 7295.28 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5442s | 0.0110s | 0.5551s |
| Unlimited | none | first improvement | 32523.88 | 7323.88 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5435s | 0.0004s | 0.5439s |
| Unlimited | none | best improvement | 32523.88 | 7323.88 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5433s | 0.0004s | 0.5437s |
| Unlimited | 2-opt | first improvement | 32416.72 | 7216.72 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5418s | 0.0019s | 0.5437s |
| Unlimited | 2-opt | best improvement | 32416.72 | 7216.72 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5435s | 0.0025s | 0.5460s |
| Unlimited | swap | first improvement | 32527.00 | 7327.00 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5416s | 0.0108s | 0.5524s |
| Unlimited | swap | best improvement | 32527.00 | 7327.00 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5435s | 0.0151s | 0.5586s |
| Unlimited | relocate | first improvement | 32495.28 | 7295.28 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5423s | 0.0089s | 0.5512s |
| Unlimited | relocate | best improvement | 32495.28 | 7295.28 | 6 | 1668 | 2077 | 660 | No | 0 | 14170 | 1229554 | 0.5429s | 0.0111s | 0.5539s |

Best objective: `2 min cap + visited-area fallback + 2-opt + first improvement` with `32416.72`.
Fastest run: `5 min cap + visited-area fallback + 2-opt + first improvement` in `0.5398s`.

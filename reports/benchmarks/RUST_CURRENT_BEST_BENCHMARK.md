# Rust Current-Best Comprehensive Benchmark

This report benchmarks the pure-Rust current-best solver across runtime budgets, cleanup operators, and first/best improvement strategies.

Pipeline: `one-location prep + pure-Rust seed route + ascending grouped strict insertion + open THM shortcut + visited-area fallback + delta-cost cleanup`.

Important difference vs Python: the Rust solver does not call the external LK package. Its seed route uses pure-Rust regret insertion plus 2-opt, so exact row-by-row routes may differ from Python.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## Old Full Data

- Orders: `data/full/PickOrder.csv`
- Stock: `data/full/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + visited-area fallback | none | first improvement | 41248.68 | 8218.68 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 1.0509s | 0.0002s | 1.0512s |
| 2 min cap + visited-area fallback | none | best improvement | 41248.68 | 8218.68 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9273s | 0.0002s | 0.9275s |
| 2 min cap + visited-area fallback | 2-opt | first improvement | 41148.16 | 8118.16 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9255s | 0.0022s | 0.9277s |
| 2 min cap + visited-area fallback | 2-opt | best improvement | 41151.60 | 8121.60 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9299s | 0.0031s | 0.9330s |
| 2 min cap + visited-area fallback | swap | first improvement | 41235.52 | 8205.52 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9442s | 0.0067s | 0.9509s |
| 2 min cap + visited-area fallback | swap | best improvement | 41235.52 | 8205.52 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9357s | 0.0078s | 0.9436s |
| 2 min cap + visited-area fallback | relocate | first improvement | 41188.36 | 8158.36 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9682s | 0.0181s | 0.9863s |
| 2 min cap + visited-area fallback | relocate | best improvement | 41188.36 | 8158.36 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9353s | 0.0229s | 0.9583s |
| 5 min cap + visited-area fallback | none | first improvement | 41248.68 | 8218.68 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9342s | 0.0002s | 0.9344s |
| 5 min cap + visited-area fallback | none | best improvement | 41248.68 | 8218.68 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9363s | 0.0002s | 0.9365s |
| 5 min cap + visited-area fallback | 2-opt | first improvement | 41148.16 | 8118.16 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9318s | 0.0022s | 0.9340s |
| 5 min cap + visited-area fallback | 2-opt | best improvement | 41151.60 | 8121.60 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9586s | 0.0034s | 0.9620s |
| 5 min cap + visited-area fallback | swap | first improvement | 41235.52 | 8205.52 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9596s | 0.0066s | 0.9662s |
| 5 min cap + visited-area fallback | swap | best improvement | 41235.52 | 8205.52 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9574s | 0.0079s | 0.9653s |
| 5 min cap + visited-area fallback | relocate | first improvement | 41188.36 | 8158.36 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9552s | 0.0188s | 0.9740s |
| 5 min cap + visited-area fallback | relocate | best improvement | 41188.36 | 8158.36 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9708s | 0.0234s | 0.9942s |
| Unlimited | none | first improvement | 41248.68 | 8218.68 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9543s | 0.0002s | 0.9545s |
| Unlimited | none | best improvement | 41248.68 | 8218.68 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9524s | 0.0002s | 0.9526s |
| Unlimited | 2-opt | first improvement | 41148.16 | 8118.16 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9460s | 0.0024s | 0.9484s |
| Unlimited | 2-opt | best improvement | 41151.60 | 8121.60 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9879s | 0.0034s | 0.9912s |
| Unlimited | swap | first improvement | 41235.52 | 8205.52 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9536s | 0.0064s | 0.9600s |
| Unlimited | swap | best improvement | 41235.52 | 8205.52 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9471s | 0.0079s | 0.9550s |
| Unlimited | relocate | first improvement | 41188.36 | 8158.36 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9821s | 0.0187s | 1.0008s |
| Unlimited | relocate | best improvement | 41188.36 | 8158.36 | 6 | 2190 | 2829 | 799 | No | 0 | 17495 | 1653495 | 0.9606s | 0.0236s | 0.9842s |
| Real pick baseline | real operation | recorded CSV + exact-style cross-floor correction | 63208.06 | 19483.06 | 6 | 2903 | 6255 | 1649 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective: `2 min cap + visited-area fallback + 2-opt + first improvement` with `41148.16`.
Fastest run: `2 min cap + visited-area fallback + none + best improvement` in `0.9275s`.
Delta vs real-operation baseline: `-22059.90` objective points.
Real-operation source: `data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv`.

## New Data

- Orders: `data/new_data/OrderData.csv`
- Stock: `data/new_data/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + visited-area fallback | none | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0026s |
| 2 min cap + visited-area fallback | none | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0030s | 0.0000s | 0.0030s |
| 2 min cap + visited-area fallback | 2-opt | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0026s |
| 2 min cap + visited-area fallback | 2-opt | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0028s | 0.0000s | 0.0028s |
| 2 min cap + visited-area fallback | swap | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0028s | 0.0000s | 0.0028s |
| 2 min cap + visited-area fallback | swap | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0026s |
| 2 min cap + visited-area fallback | relocate | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0027s | 0.0000s | 0.0027s |
| 2 min cap + visited-area fallback | relocate | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0029s | 0.0000s | 0.0029s |
| 5 min cap + visited-area fallback | none | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0026s |
| 5 min cap + visited-area fallback | none | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0029s | 0.0000s | 0.0029s |
| 5 min cap + visited-area fallback | 2-opt | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0026s |
| 5 min cap + visited-area fallback | 2-opt | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0026s |
| 5 min cap + visited-area fallback | swap | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0029s | 0.0000s | 0.0029s |
| 5 min cap + visited-area fallback | swap | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0027s | 0.0000s | 0.0028s |
| 5 min cap + visited-area fallback | relocate | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0029s | 0.0000s | 0.0029s |
| 5 min cap + visited-area fallback | relocate | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0027s |
| Unlimited | none | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0028s | 0.0000s | 0.0028s |
| Unlimited | none | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0027s | 0.0000s | 0.0027s |
| Unlimited | 2-opt | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0028s | 0.0000s | 0.0029s |
| Unlimited | 2-opt | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0028s | 0.0000s | 0.0028s |
| Unlimited | swap | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0026s |
| Unlimited | swap | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0028s | 0.0000s | 0.0029s |
| Unlimited | relocate | first improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0026s |
| Unlimited | relocate | best improvement | 1896.92 | 966.92 | 4 | 54 | 80 | 34 | No | 0 | 447 | 3525 | 0.0026s | 0.0000s | 0.0026s |
| Real pick baseline | real operation | actual selected locations re-routed with shared route builder | 3514.04 | 1654.04 | 4 | 116 | 196 | 74 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Best objective: `2 min cap + visited-area fallback + none + first improvement` with `1896.92`.
Fastest run: `Unlimited + relocate + first improvement` in `0.0026s`.
Delta vs real-operation baseline: `-1617.12` objective points.
Real-operation source: `data/new_data/PickData.csv`.

## 4000 Sample

- Orders: `data/4000_sample/PickOrder_sample_4000.csv`
- Stock: `data/4000_sample/StockData.csv`

| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |
|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 min cap + visited-area fallback | none | first improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6641s | 0.0002s | 0.6642s |
| 2 min cap + visited-area fallback | none | best improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6588s | 0.0002s | 0.6590s |
| 2 min cap + visited-area fallback | 2-opt | first improvement | 32388.80 | 7278.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6602s | 0.0017s | 0.6619s |
| 2 min cap + visited-area fallback | 2-opt | best improvement | 32388.80 | 7278.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6578s | 0.0020s | 0.6597s |
| 2 min cap + visited-area fallback | swap | first improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6573s | 0.0038s | 0.6610s |
| 2 min cap + visited-area fallback | swap | best improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6581s | 0.0057s | 0.6637s |
| 2 min cap + visited-area fallback | relocate | first improvement | 32448.40 | 7338.40 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6527s | 0.0070s | 0.6597s |
| 2 min cap + visited-area fallback | relocate | best improvement | 32448.40 | 7338.40 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6515s | 0.0080s | 0.6595s |
| 5 min cap + visited-area fallback | none | first improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6408s | 0.0002s | 0.6410s |
| 5 min cap + visited-area fallback | none | best improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6721s | 0.0002s | 0.6723s |
| 5 min cap + visited-area fallback | 2-opt | first improvement | 32388.80 | 7278.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6445s | 0.0015s | 0.6460s |
| 5 min cap + visited-area fallback | 2-opt | best improvement | 32388.80 | 7278.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6381s | 0.0019s | 0.6400s |
| 5 min cap + visited-area fallback | swap | first improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6418s | 0.0035s | 0.6453s |
| 5 min cap + visited-area fallback | swap | best improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6424s | 0.0054s | 0.6478s |
| 5 min cap + visited-area fallback | relocate | first improvement | 32448.40 | 7338.40 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6368s | 0.0069s | 0.6437s |
| 5 min cap + visited-area fallback | relocate | best improvement | 32448.40 | 7338.40 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6418s | 0.0078s | 0.6496s |
| Unlimited | none | first improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6457s | 0.0002s | 0.6459s |
| Unlimited | none | best improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6409s | 0.0002s | 0.6411s |
| Unlimited | 2-opt | first improvement | 32388.80 | 7278.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6407s | 0.0015s | 0.6422s |
| Unlimited | 2-opt | best improvement | 32388.80 | 7278.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6417s | 0.0019s | 0.6436s |
| Unlimited | swap | first improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6382s | 0.0034s | 0.6416s |
| Unlimited | swap | best improvement | 32459.80 | 7349.80 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6426s | 0.0053s | 0.6479s |
| Unlimited | relocate | first improvement | 32448.40 | 7338.40 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6818s | 0.0070s | 0.6888s |
| Unlimited | relocate | best improvement | 32448.40 | 7338.40 | 6 | 1662 | 2074 | 669 | No | 0 | 14118 | 1245642 | 0.6483s | 0.0078s | 0.6561s |

Best objective: `2 min cap + visited-area fallback + 2-opt + first improvement` with `32388.80`.
Fastest run: `5 min cap + visited-area fallback + 2-opt + best improvement` in `0.6400s`.

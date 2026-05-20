# C++ Bucket-Cheapest Width Benchmark

This report benchmarks the bucket-cheapest article selection mode on the full dataset.

Pipeline: `one-location prep + LKH-3 seed route + bucket/global strict cheapest insertion + GRASP fallback if capped + delta-cost cleanup`.

Common objective: `distance + 15 * opened THMs + 30 * active floors`.

## Setup

- Orders: `data/full/PickOrder.csv`
- Stock: `data/full/StockData.csv`
- Demand articles: `2759`
- Total demand amount: `6816`
- Stock rows / stock articles: `26707` / `2997`
- Runtime cap: `120s` with GRASP fallback enabled
- Seed route: `LKH-3 explicit full-matrix depot cycle`
- Cleanup: `2-opt` / `best` / `3` passes

Width `0` is the all-remaining global-cheapest baseline. Widths `1-5` use bucket-cheapest, where buckets are processed in candidate-count order and the cheapest strict insertion is selected within the active bucket.

## Results

| Width | Mode | Candidate buckets | Objective | Delta vs best | Distance | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict steps | Strict evals | Position evals | Cleanup passes | Selection time | Cleanup time | Total time |
|---:|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | `global-cheapest` | `all remaining` | 41196.80 | 646.64 | 8076.80 | 2196 | 2815 | 900 | Yes | 3750 | 431 | 9607834 | 471613476 | 10 | 119.59s | 0.0041s | 120.12s |
| 1 | `bucket-cheapest` | `2, 3, 4, ...` | 40783.20 | 233.04 | 7918.20 | 2179 | 2828 | 801 | No | 0 | 2517 | 1044569 | 83173403 | 8 | 30.90s | 0.0028s | 31.36s |
| 2 | `bucket-cheapest` | `2-3, 4-5, ...` | 40550.16 | 0.00 | 7910.16 | 2164 | 2827 | 795 | No | 0 | 2516 | 2057052 | 158838454 | 6 | 58.14s | 0.0026s | 58.59s |
| 3 | `bucket-cheapest` | `2-4, 5-7, ...` | 41024.20 | 474.04 | 8024.20 | 2188 | 2824 | 816 | No | 0 | 2513 | 3050444 | 232750712 | 7 | 84.43s | 0.0028s | 84.89s |
| 4 | `bucket-cheapest` | `2-5, 6-9, ...` | 41272.56 | 722.40 | 8077.56 | 2201 | 2827 | 823 | No | 0 | 2516 | 4027787 | 296043465 | 5 | 105.30s | 0.0027s | 105.76s |
| 5 | `bucket-cheapest` | `2-6, 7-11, ...` | 41476.44 | 926.28 | 8086.44 | 2214 | 2824 | 839 | Yes | 659 | 2310 | 4885396 | 347063958 | 7 | 119.58s | 0.0029s | 120.04s |

## Takeaways

- Best objective: width `2` with `40550.16`.
- Fastest run: width `1` in `31.36s`.
- Width `0` and any capped rows include GRASP fallback, so they are not pure strict-cheapest completions.
- Width `2` completed without fallback in `58.59s` and is the current strongest bucket-cheapest candidate in this sweep.

## Output Files

- Run outputs: `outputs/benchmark_outputs/cpp_bucket_cheapest_width_benchmark`
- Summary JSON: `outputs/benchmark_outputs/cpp_bucket_cheapest_width_benchmark/run_summary.json`

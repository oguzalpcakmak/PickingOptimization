# C++ Candidate Group Width Benchmark

This report benchmarks how the C++ current-best solver changes when remaining articles are bucketed by candidate-location count.

Pipeline: `one-location prep + LKH-3 seed route + candidate-count bucketed strict insertion + open THM shortcut + GRASP fallback + delta-cost cleanup`.

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

A width of `1` is the old exact-count order: `2`, then `3`, then `4`, etc. A width of `10` means `2-11`, then `12-21`, etc.

## Results

| Width | Candidate buckets | Objective | Delta vs best | Delta vs width 1 | Distance | THMs | Pick rows | Visited nodes | Strict evals | Position evals | Fast reuse | Cleanup passes | Seed time | Grouped time | Cleanup time | Total time |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `2, 3, 4, ...` | 41057.32 | 0.00 | 0.00 | 8117.32 | 2184 | 2830 | 810 | 17418 | 1649175 | 628 | 8 | 0.6357s | 0.7383s | 0.0033s | 1.4529s |
| 2 | `2-3, 4-5, 6-7, ...` | 41126.04 | 68.72 | 68.72 | 8111.04 | 2189 | 2827 | 803 | 17460 | 1656568 | 620 | 4 | 0.4890s | 0.9524s | 0.0027s | 1.5072s |
| 3 | `2-4, 5-7, 8-10, ...` | 41128.12 | 70.80 | 70.80 | 8173.12 | 2185 | 2825 | 816 | 17482 | 1652530 | 622 | 5 | 0.4474s | 0.9187s | 0.0029s | 1.4372s |
| 4 | `2-5, 6-9, 10-13, ...` | 41231.88 | 174.56 | 174.56 | 8201.88 | 2190 | 2826 | 824 | 17386 | 1628433 | 618 | 7 | 0.4424s | 0.9160s | 0.0038s | 1.4254s |
| 5 | `2-6, 7-11, 12-16, ...` | 41382.64 | 325.32 | 325.32 | 8232.64 | 2198 | 2829 | 826 | 17491 | 1638619 | 613 | 9 | 0.4627s | 0.9501s | 0.0036s | 1.4801s |
| 6 | `2-7, 8-13, 14-19, ...` | 41422.64 | 365.32 | 365.32 | 8272.64 | 2198 | 2827 | 840 | 17697 | 1679001 | 611 | 9 | 0.4563s | 0.9196s | 0.0036s | 1.4673s |
| 7 | `2-8, 9-15, 16-22, ...` | 41653.44 | 596.12 | 596.12 | 8278.44 | 2213 | 2825 | 840 | 17931 | 1680894 | 594 | 9 | 0.4495s | 1.0850s | 0.0035s | 1.5969s |
| 8 | `2-9, 10-17, 18-25, ...` | 41773.44 | 716.12 | 716.12 | 8278.44 | 2221 | 2823 | 843 | 17957 | 1674944 | 584 | 9 | 0.5392s | 1.0716s | 0.0037s | 1.6755s |
| 9 | `2-10, 11-19, 20-28, ...` | 41685.20 | 627.88 | 627.88 | 8280.20 | 2215 | 2824 | 842 | 17838 | 1661144 | 591 | 6 | 0.4554s | 0.8982s | 0.0035s | 1.4166s |
| 10 | `2-11, 12-21, 22-31, ...` | 41784.40 | 727.08 | 727.08 | 8274.40 | 2222 | 2824 | 859 | 18019 | 1681889 | 584 | 9 | 0.4499s | 0.9850s | 0.0058s | 1.5049s |
| 11 | `2-12, 13-23, 24-34, ...` | 41865.20 | 807.88 | 807.88 | 8280.20 | 2227 | 2824 | 862 | 18146 | 1680345 | 579 | 9 | 0.4431s | 0.9175s | 0.0040s | 1.4251s |
| 12 | `2-13, 14-25, 26-37, ...` | 41985.20 | 927.88 | 927.88 | 8280.20 | 2235 | 2823 | 864 | 18312 | 1692198 | 570 | 9 | 0.4286s | 0.8727s | 0.0037s | 1.3680s |
| 13 | `2-14, 15-27, 28-40, ...` | 42030.20 | 972.88 | 972.88 | 8280.20 | 2238 | 2822 | 866 | 18354 | 1691873 | 566 | 9 | 0.4457s | 1.0026s | 0.0040s | 1.5132s |
| 14 | `2-15, 16-29, 30-43, ...` | 42060.20 | 1002.88 | 1002.88 | 8280.20 | 2240 | 2821 | 867 | 18414 | 1687656 | 563 | 9 | 0.4873s | 0.8988s | 0.0038s | 1.4572s |
| 15 | `2-16, 17-31, 32-46, ...` | 42101.80 | 1044.48 | 1044.48 | 8291.80 | 2242 | 2821 | 870 | 18299 | 1674612 | 561 | 9 | 0.4797s | 0.8811s | 0.0045s | 1.4368s |

## Takeaways

- Best objective: width `1` with `41057.32`.
- Fastest run: width `12` in `1.3680s`.
- Width `1` baseline objective: `41057.32`.
- Worst objective in this sweep: width `15` with `42101.80`.
- No run hit the runtime cap or needed fallback.

## Output Files

- Run outputs: `outputs/benchmark_outputs/cpp_candidate_group_width_benchmark`
- Summary JSON: `outputs/benchmark_outputs/cpp_candidate_group_width_benchmark/run_summary.json`

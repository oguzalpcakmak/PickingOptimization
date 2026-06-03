# Gurobi vs C++ Heuristic: 25-Item / 3-Floor Unlimited Benchmark

## Scope

This report records the unlimited Gurobi benchmark run and the subsequent C++ heuristic comparison from the terminal output.

- Profile: `25item3floor`
- Floors allowed: `MZN1, MZN2, MZN3`
- Articles: `567, 577, 606, 609, 699, 788, 791, 866, 977, 993, 997, 999, 1019, 1020, 1030, 1051, 1055, 1061, 1066, 1068, 1087, 1088, 1093, 1118, 1122`
- Article count: `25`
- Total pick amount: `71`
- Objective: `distance + 15 * THMs + 30 * active floors`
- Command:

```bash
python3 src/benchmark_gurobi_cpp.py --profile 25item3floor --time-limit 0
```

## Result Summary

| Solver | Status | Objective | Distance | Active floors | Opened THMs | Pick rows | Visited nodes | Runtime |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Corrected Gurobi MIP model | `OPTIMAL` | **856.10** | 466.10 m | 1 | 24 | 25 | 23 | 2718.59s |
| C++ current heuristic | `COMPLETED` | 888.42 | 498.42 m | 1 | 24 | 25 | 22 | 0.05s |

The C++ heuristic is `32.32` objective points, or `3.78%`, above the proven Gurobi optimum.

## Gurobi Model

| Metric | Value |
| --- | ---: |
| Constraints | 10,072 |
| Variables | 9,554 |
| Non-zero coefficients | 46,498 |
| Continuous variables | 156 |
| Integer variables | 9,223 |
| Binary variables | 9,223 |
| Semi-integer variables | 175 |
| Explored branch-and-bound nodes | 2,925,404 |
| Simplex iterations | 82,912,508 |
| Work units | 5,956.22 |
| Threads | 8 |

## Gurobi Progress

The incumbent is the best feasible objective found so far. The best bound is the proven lower bound for this minimization problem. Optimality is proven when both values meet.

| Elapsed time | Incumbent | Best bound | Remaining gap | Explored nodes | Note |
| ---: | ---: | ---: | ---: | ---: | --- |
| 10s | 861.90 | 730.28 | 15.30% | 1,656 | Strong feasible solution found quickly |
| 24s | 860.34 | 777.76 | 9.60% | 2,463 | Previous long-run incumbent reached |
| 120s | 860.34 | 802.13 | 6.77% | 29,919 | Bound tightening continues |
| 300s | 860.34 | 823.35 | 4.30% | 202,468 | No incumbent improvement yet |
| 600s | 860.34 | 830.86 | 3.43% | 518,157 | Ten-minute checkpoint |
| 685s | 856.30 | 832.25 | 2.81% | 618,078 | Better feasible solution found |
| 719s | **856.10** | 832.83 | 2.72% | 656,676 | Final optimal objective first found |
| 900s | 856.10 | 835.79 | 2.37% | 861,378 | Proof phase continues |
| 1,191s | 856.10 | 839.59 | 1.93% | 1,198,511 | Bound tightening |
| 1,500s | 856.10 | 841.37 | 1.72% | 1,414,324 | Bound tightening |
| 1,785s | 856.10 | 843.99 | 1.41% | 1,782,355 | Bound tightening |
| 2,090s | 856.10 | 846.55 | 1.12% | 2,165,463 | Bound tightening |
| 2,400s | 856.10 | 849.84 | 0.73% | 2,601,525 | Final proof stretch |
| 2,696s | 856.10 | 854.10 | 0.23% | 2,890,404 | Near convergence |
| 2,718.59s | **856.10** | **856.10** | **0.00%** | **2,925,404** | Optimality proven |

## Timing Interpretation

- Gurobi found the final optimal objective after approximately `719s`, or `11m 59s`.
- Gurobi needed approximately `2718.59s`, or `45m 19s`, to prove that no better solution exists.
- The final proof phase therefore took roughly `33m 20s` after the optimal feasible solution had already been found.
- The C++ heuristic completed in approximately `0.05s` and remained within `3.78%` of the proven optimum.

## C++ Configuration

| Setting | Value |
| --- | --- |
| Article selection | `bucket-cheapest` |
| Candidate group width | `2` |
| Seed route optimizer | `lkh` |
| Seed route | `LKH-3 explicit full-matrix depot cycle` |
| Route cleanup | `2-opt (best)` |
| Strict candidate evaluations | `609` |
| Strict position evaluations | `3,449` |
| Fallback used | `false` |

## Conclusion

The unlimited Gurobi run establishes `856.10` as the exact optimum for this 25-item profile under the current `1 / 15 / 30` objective. The C++ heuristic reaches `888.42` in a fraction of a second, making it a practical fast-solve option while remaining close to the exact optimum on this benchmark.

Legacy `1 / 1 / 1` benchmark objectives are not directly comparable with this run.

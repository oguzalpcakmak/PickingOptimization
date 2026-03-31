# 25-Item / 3-Floor Benchmark Comparison

This report compares the saved repository benchmark plan, the exact Gurobi run, the existing heuristic, and the two new heuristic alternatives on the same 25-item / 3-floor configuration.

## Benchmark Setup

- Orders: `25item3floor/PickOrder.csv`
- Stock: `25item3floor/StockData.csv`
- Floors: `MZN1,MZN2,MZN3`
- Articles:
  `567,577,606,609,699,788,791,866,977,993,997,999,1019,1020,1030,1051,1055,1061,1066,1068,1087,1088,1093,1118,1122`
- Objective weights used for the run:
  `distance = 1`, `thm = 1`, `floor = 1`

## Side-by-Side Results

The main comparison column below is `Comparable Objective`, which rescored every output using the same depot-anchored route evaluator:

`Comparable Objective = Total Distance + Opened THMs + Active Floors`

This matters because the older `betul-heuristic.py` reports a larger native distance/objective than the exact-style rescored value.

| Solver / Plan | Comparable Objective | Native Reported Objective | Distance | Floors | THMs | Pick Rows | Visited Nodes | Solve Time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Saved repo reference | 491.10 | n/a | 466.10 | 1 | 24 | 25 | 24 | n/a |
| Exact Gurobi, 30s limit | 508.72 | 508.72 | 482.72 | 2 | 24 | 26 | 21 | 30.0s |
| GRASP multi-start | 520.50 | 520.50 | 495.50 | 1 | 24 | 25 | 23 | 1.43s |
| Route-aware regret greedy | 569.84 | 569.84 | 543.84 | 2 | 24 | 26 | 23 | 0.16s |
| THM-min + RR-style aisle DP | 664.72 | 664.72 | 639.72 | 2 | 23 | 26 | 19 | 10.15s |
| Existing Betul heuristic | 781.60 | 4077.96 | 747.60 | 2 | 32 | 33 | 32 | 0.14s |

## Ranking

1. Saved repo reference: `491.10`
2. Exact Gurobi, 30-second incumbent: `508.72`
3. GRASP multi-start: `520.50`
4. Route-aware regret greedy: `569.84`
5. THM-min + RR-style aisle DP: `664.72`
6. Existing Betul heuristic: `781.60`

## Notes

- The saved repository benchmark plan is currently the strongest solution in this comparison.
- The exact Gurobi run was time-limited to 30 seconds and stopped with a remaining optimality gap, so `508.72` is a best incumbent, not a proven optimum.
- The new GRASP heuristic is the strongest heuristic on this benchmark and comes fairly close to the saved reference while staying fast.
- The new deterministic regret heuristic is much stronger than the existing Betul heuristic and remains very fast.
- The THM-min + RR-style solver does exactly what it is designed to do: it pushes THM count down first. On this benchmark it found a 23-THM incumbent, but that came with a much longer route, so its total objective is worse than the GRASP and regret heuristics.
- The THM-min phase was not proven optimal within the 10-second search budget on this run, so the 23-THM solution is the best incumbent found, not a proof that 23 is the true minimum.
- The existing Betul heuristic's own printed objective is not directly comparable to the exact model because its total distance accounting is different. The `Comparable Objective` column corrects that by rescoring its exported route.

## Source Files

- Saved repo reference pick list: [ThreeFloor25PickData.csv](./ThreeFloor25PickData.csv)
- Saved repo reference alternatives: [ThreeFloor25Alternatives.csv](./ThreeFloor25Alternatives.csv)
- Existing heuristic implementation: [../betul-heuristic.py](../betul-heuristic.py)
- New regret heuristic: [../regret_based_heuristic.py](../regret_based_heuristic.py)
- New GRASP heuristic: [../grasp_heuristic.py](../grasp_heuristic.py)
- New THM-min + RR-style heuristic: [../thm_min_rr_heuristic.py](../thm_min_rr_heuristic.py)
- Shared heuristic utilities: [../heuristic_common.py](../heuristic_common.py)

## Generated Run Artifacts

- Exact Gurobi pick list: [/tmp/exact_25_3floor.csv](/tmp/exact_25_3floor.csv)
- Exact Gurobi alternatives: [/tmp/exact_25_3floor_alt.csv](/tmp/exact_25_3floor_alt.csv)
- Existing Betul heuristic pick list: [/tmp/betul_25_3floor.csv](/tmp/betul_25_3floor.csv)
- Existing Betul heuristic alternatives: [/tmp/betul_25_3floor_alt.csv](/tmp/betul_25_3floor_alt.csv)
- Regret heuristic pick list: [/tmp/regret_25_3floor.csv](/tmp/regret_25_3floor.csv)
- Regret heuristic alternatives: [/tmp/regret_25_3floor_alt.csv](/tmp/regret_25_3floor_alt.csv)
- GRASP heuristic pick list: [/tmp/grasp_25_3floor.csv](/tmp/grasp_25_3floor.csv)
- GRASP heuristic alternatives: [/tmp/grasp_25_3floor_alt.csv](/tmp/grasp_25_3floor_alt.csv)
- THM-min + RR-style heuristic pick list: [/tmp/thm_rr_25_3floor.csv](/tmp/thm_rr_25_3floor.csv)
- THM-min + RR-style heuristic alternatives: [/tmp/thm_rr_25_3floor_alt.csv](/tmp/thm_rr_25_3floor_alt.csv)

## Commands Used

### Exact Gurobi

```bash
./run_solver.sh \
  --orders 25item3floor/PickOrder.csv \
  --stock 25item3floor/StockData.csv \
  --floors MZN1,MZN2,MZN3 \
  --articles 567,577,606,609,699,788,791,866,977,993,997,999,1019,1020,1030,1051,1055,1061,1066,1068,1087,1088,1093,1118,1122 \
  --distance-weight 1 \
  --thm-weight 1 \
  --floor-weight 1 \
  --time-limit 30 \
  --optimize \
  --pick-data-output /tmp/exact_25_3floor.csv \
  --alternative-locations-output /tmp/exact_25_3floor_alt.csv
```

### Existing Betul Heuristic

```bash
.venv/bin/python betul-heuristic.py \
  --orders 25item3floor/PickOrder.csv \
  --stock 25item3floor/StockData.csv \
  --floors MZN1,MZN2,MZN3 \
  --articles 567,577,606,609,699,788,791,866,977,993,997,999,1019,1020,1030,1051,1055,1061,1066,1068,1087,1088,1093,1118,1122 \
  --distance-weight 1 \
  --thm-weight 1 \
  --floor-weight 1 \
  --output /tmp/betul_25_3floor.csv \
  --alternative-locations-output /tmp/betul_25_3floor_alt.csv
```

### Route-Aware Regret Greedy

```bash
.venv/bin/python regret_based_heuristic.py \
  --orders 25item3floor/PickOrder.csv \
  --stock 25item3floor/StockData.csv \
  --floors MZN1,MZN2,MZN3 \
  --articles 567,577,606,609,699,788,791,866,977,993,997,999,1019,1020,1030,1051,1055,1061,1066,1068,1087,1088,1093,1118,1122 \
  --distance-weight 1 \
  --thm-weight 1 \
  --floor-weight 1 \
  --output /tmp/regret_25_3floor.csv \
  --alternative-locations-output /tmp/regret_25_3floor_alt.csv
```

### GRASP Multi-Start

```bash
.venv/bin/python grasp_heuristic.py \
  --orders 25item3floor/PickOrder.csv \
  --stock 25item3floor/StockData.csv \
  --floors MZN1,MZN2,MZN3 \
  --articles 567,577,606,609,699,788,791,866,977,993,997,999,1019,1020,1030,1051,1055,1061,1066,1068,1087,1088,1093,1118,1122 \
  --distance-weight 1 \
  --thm-weight 1 \
  --floor-weight 1 \
  --iterations 100 \
  --time-limit 5 \
  --output /tmp/grasp_25_3floor.csv \
  --alternative-locations-output /tmp/grasp_25_3floor_alt.csv
```

### THM-Min + RR-Style Aisle DP

```bash
.venv/bin/python thm_min_rr_heuristic.py \
  --orders 25item3floor/PickOrder.csv \
  --stock 25item3floor/StockData.csv \
  --floors MZN1,MZN2,MZN3 \
  --articles 567,577,606,609,699,788,791,866,977,993,997,999,1019,1020,1030,1051,1055,1061,1066,1068,1087,1088,1093,1118,1122 \
  --distance-weight 1 \
  --thm-weight 1 \
  --floor-weight 1 \
  --thm-search-time-limit 10 \
  --output /tmp/thm_rr_25_3floor.csv \
  --alternative-locations-output /tmp/thm_rr_25_3floor_alt.csv
```

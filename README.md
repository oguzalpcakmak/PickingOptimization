# Picking Optimization

Warehouse picking optimization experiments for exact, greedy, GRASP, THM-first, VNS/LNS/ALNS, and route-cleanup heuristics.

Start here: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

Recommended current-best run:

```bash
.venv/bin/python src/current_best_heuristic.py \
  --orders data/full/PickOrder.csv \
  --stock data/full/StockData.csv \
  --time-limit 300 \
  --output outputs/benchmark_outputs/manual/current_best_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/manual/current_best_alt.csv \
  --summary-output outputs/benchmark_outputs/manual/current_best_summary.json
```

Quick GRASP run:

```bash
.venv/bin/python src/grasp_heuristic.py \
  --orders data/full/PickOrder.csv \
  --stock data/full/StockData.csv \
  --output outputs/benchmark_outputs/manual/grasp_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/manual/grasp_alt.csv
```

Benchmark reports are under `reports/benchmarks/`; generated CSV/JSON outputs are under `outputs/benchmark_outputs/`.

Rust speed-experiment solver:

```bash
cd rust_solver
cargo run --release -- \
  --orders ../data/full/PickOrder.csv \
  --stock ../data/full/StockData.csv \
  --time-limit 300 \
  --output ../outputs/benchmark_outputs/rust_current_best/current_best_pick.csv \
  --alternative-locations-output ../outputs/benchmark_outputs/rust_current_best/current_best_alt.csv \
  --summary-output ../outputs/benchmark_outputs/rust_current_best/current_best_summary.json
```

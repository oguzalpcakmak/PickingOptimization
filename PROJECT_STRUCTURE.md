# Project Structure

This repository is organized so solver code, datasets, generated outputs, and written reports are easier to find.

## Top-Level Folders

| Path | Purpose |
|---|---|
| `src/` | Python solvers, shared heuristic utilities, benchmark runners, and launcher code. |
| `data/full/` | Main full dataset: `PickOrder.csv` and `StockData.csv`. |
| `data/new_data/` | Corrected new dataset: `OrderData.csv`, `StockData.csv`, `PickData.csv`. |
| `data/4000_sample/` | 4000-unit sample dataset. |
| `data/25item3floor/` | Original 25-item / 3-floor test dataset and its local benchmark files. |
| `data/legacy_samples/` | Older sample CSVs and historical solver outputs that used to live in the repo root. |
| `data/real_pick/` | Real/historical pick-operation data. |
| `outputs/benchmark_outputs/` | Generated benchmark outputs, pick CSVs, alternative CSVs, summaries, and smoke-test outputs. |
| `config/` | Local/private configuration files such as API keys. These are ignored by git. |
| `reports/benchmarks/` | Benchmark comparison markdown/html reports. |
| `docs/algorithms/` | Algorithm explanations and presentation-oriented notes. |
| `docs/approaches/` | Approach-review markdown files. |
| `docs/model/` | Mathematical/model notes such as `Model.tex`. |
| `notebooks/` | Colab/Jupyter notebooks. |
| `external/` | Third-party or imported research/reference repositories. |
| `rust_solver/` | Pure Rust speed-experiment implementation of the current-best heuristic. |
| `Simulation/` | React visualization app, kept in its original folder. |

## Common Commands

Run GRASP on the full dataset:

```bash
.venv/bin/python src/grasp_heuristic.py \
  --orders data/full/PickOrder.csv \
  --stock data/full/StockData.csv \
  --output outputs/benchmark_outputs/manual/grasp_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/manual/grasp_alt.csv
```

Run the current best practical combination:

```bash
.venv/bin/python src/current_best_heuristic.py \
  --orders data/full/PickOrder.csv \
  --stock data/full/StockData.csv \
  --time-limit 300 \
  --cleanup-operator 2-opt \
  --cleanup-strategy best \
  --output outputs/benchmark_outputs/manual/current_best_pick.csv \
  --alternative-locations-output outputs/benchmark_outputs/manual/current_best_alt.csv \
  --summary-output outputs/benchmark_outputs/manual/current_best_summary.json
```

Run the Rust speed-experiment version:

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

Run the exact solver wrapper:

```bash
./run_solver.sh \
  --orders data/full/PickOrder.csv \
  --stock data/full/StockData.csv \
  --time-limit 120 \
  --optimize
```

Run the runtime fallback benchmark:

```bash
.venv/bin/python src/runtime_fallback_benchmark.py
```

Run the first-vs-best improvement benchmark:

```bash
.venv/bin/python src/runtime_fallback_improvement_strategy_benchmark.py
```

Run the React visualization app:

```bash
cd Simulation
npm run dev
```

## Notes

- Most Python scripts now default to `data/full/PickOrder.csv` and `data/full/StockData.csv`.
- Benchmark scripts default to writing under `outputs/benchmark_outputs/`.
- Historical reports were moved under `reports/benchmarks/`; some older narrative references may still mention the previous root-level filenames for context.

# Rust Current-Best Solver

Pure Rust implementation of the practical current-best warehouse picking pipeline:

1. Commit one-location articles first.
2. Build a pure-Rust seed route for those picks.
3. Process remaining articles by ascending candidate-count groups.
4. Prefer already-open THMs before strict cheapest insertion.
5. Complete with GRASP-style fallback if a time cap is reached.
6. Apply delta-cost route cleanup, defaulting to best-improvement 2-opt.

The Python implementation is still the reference. This Rust solver is designed for speed experiments and writes the same pick/alternative CSV shapes.

## Build

```bash
cargo build --release
```

## Run Full Data

From this folder:

```bash
cargo run --release -- \
  --orders ../data/full/PickOrder.csv \
  --stock ../data/full/StockData.csv \
  --time-limit 300 \
  --output ../outputs/benchmark_outputs/rust_current_best/current_best_pick.csv \
  --alternative-locations-output ../outputs/benchmark_outputs/rust_current_best/current_best_alt.csv \
  --summary-output ../outputs/benchmark_outputs/rust_current_best/current_best_summary.json
```

## Notes

- This version intentionally avoids third-party crates, so it can build without downloading dependencies.
- The external Python LK package is not used; the seed route is replaced with a pure-Rust regret insertion plus 2-opt seed.
- Because the seed route differs from Python's LK seed, exact route/order results may differ slightly even when the objective logic is the same.

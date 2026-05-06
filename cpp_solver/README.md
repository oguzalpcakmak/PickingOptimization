# C++ Current-Best Solver

Dependency-free C++17 port of the practical warehouse picking heuristic.

Pipeline:

1. Commit one-location articles first.
2. Build a pure C++ seed route with regret insertion plus 2-opt.
3. Process remaining articles by ascending candidate-count groups.
4. Prefer already-open THMs before strict cheapest insertion.
5. Complete with the selected fallback if a time cap is reached.
6. Apply delta-cost route cleanup.

## Build

From this folder:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

If CMake is not installed, from the repository root:

```bash
mkdir -p cpp_solver/build
c++ -std=c++17 -O3 -Wall -Wextra -pedantic \
  cpp_solver/src/main.cpp \
  -o cpp_solver/build/picking_current_best_cpp
```

## Run

From this folder:

```bash
./build/picking_current_best_cpp \
  --orders ../data/full/PickOrder.csv \
  --stock ../data/full/StockData.csv \
  --time-limit 300 \
  --fallback-method visited-area \
  --cleanup-operator 2-opt \
  --cleanup-strategy best \
  --output ../outputs/benchmark_outputs/cpp_current_best/current_best_pick.csv \
  --alternative-locations-output ../outputs/benchmark_outputs/cpp_current_best/current_best_alt.csv \
  --summary-output ../outputs/benchmark_outputs/cpp_current_best/current_best_summary.json
```

Fallback options:

- `--fallback-method grasp`: original GRASP-style RCL completion.
- `--fallback-method visited-area`: v2 rule, prioritizing visited box, half-block, aisle, floor, then random.

Cleanup options:

- `--cleanup-operator none|2-opt|swap|relocate`
- `--cleanup-strategy first|best`

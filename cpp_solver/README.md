# C++ Current-Best Solver

C++17 port of the practical warehouse picking heuristic. It uses the external
LKH-3 executable for the one-location seed route by default, with the old pure
C++ seed route still available as a fallback option.

Pipeline:

1. Commit one-location articles first.
2. Build the seed route with LKH-3 over an explicit warehouse distance matrix.
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
  --seed-route-optimizer lkh \
  --lkh-path ../external/LKH-3.0.14/LKH \
  --article-selection grouped \
  --candidate-group-width 2 \
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

Seed route options:

- `--seed-route-optimizer lkh`: default; writes a TSPLIB full-matrix problem per seed floor and calls LKH-3.
- `--seed-route-optimizer cpp`: previous pure C++ regret insertion plus 2-opt seed route.
- `--lkh-path PATH`: path to the LKH executable. If omitted, the solver looks for `external/LKH-3.0.14/LKH` from the repository root or `../external/LKH-3.0.14/LKH` from `cpp_solver/`.
- `--article-selection grouped`: default; processes remaining articles by candidate-count buckets and uses the open-THM shortcut.
- `--article-selection bucket-cheapest`: processes candidate-count buckets in order, but within each bucket commits the globally cheapest strict insertion.
- `--article-selection global-cheapest`: evaluates every remaining article-location candidate with strict insertion at each step and commits the global cheapest candidate.
- `--candidate-group-width N`: groups remaining articles by candidate-count buckets. The default `2` processes `2-3`, then `4-5`, then `6-7`, etc. Use `1` for the old exact-count order.

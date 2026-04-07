# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Warehouse picking optimization system for METU Systems Design course. Solves multi-floor order picking with multiple approaches: exact optimization (Gurobi), and several heuristics (GRASP, regret-based, THM-minimization).

## Environment Setup

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (if needed)
pip install gurobipy pandas numpy
```

## Running Solvers

### Heuristic Solvers (Fast)

**GRASP Multi-Start** (best heuristic, ~1-20s):
```bash
.venv/bin/python grasp_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output pick_output.csv \
  --alternative-locations-output alt_output.csv
```

**Regret-Based Greedy** (deterministic, very fast ~0.2s):
```bash
.venv/bin/python regret_based_heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output pick_output.csv \
  --alternative-locations-output alt_output.csv
```

**Existing Betul Heuristic** (legacy, fast but weaker):
```bash
.venv/bin/python betul-heuristic.py \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output pick_output.csv \
  --alternative-locations-output alt_output.csv
```

**THM-Minimization Variants** (prioritize minimizing THM count):
```bash
# RR-style aisle routing
.venv/bin/python thm_min_rr_heuristic.py --orders ... --stock ...

# S-shape routing
.venv/bin/python thm_min_s_shape_heuristic.py --orders ... --stock ...
```

### Exact Solver (Slow, requires Gurobi license)

```bash
./run_solver.sh \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --distance-weight 1 \
  --thm-weight 15 \
  --floor-weight 30 \
  --time-limit 120 \
  --optimize \
  --pick-data-output exact_pick.csv \
  --alternative-locations-output exact_alt.csv
```

### Filtering by Floors/Articles

All solvers support:
```bash
--floors MZN1,MZN2,MZN3
--articles 567,577,606,609,699  # comma-separated article codes
```

## Visualization (React Web App)

```bash
cd Simulation
npm install
npm run dev  # Runs on http://localhost:5173
npm run build  # Production build
```

The web app visualizes picking routes from CSV outputs. Upload Excel files with "Grup Toplama Verisi" sheet containing columns: `Kullanıcı Kodu`, `PICKCAR_THM`, `AISLE`, `X`, `Y`, `Z`, etc.

## Architecture

### Python Solvers

- **gurobi_pick_model.py**: Exact MIP model with Gurobi
- **grasp_heuristic.py**: GRASP multi-start with controlled randomization
- **regret_based_heuristic.py**: Deterministic regret-based greedy
- **betul-heuristic.py**: Original heuristic (legacy)
- **thm_min_rr_heuristic.py**: THM-first with RR-style aisle routing
- **thm_min_s_shape_heuristic.py**: THM-first with S-shape routing
- **heuristic_common.py**: Shared utilities (distance calc, route optimization, data loading)

### Objective Function

All solvers optimize:
```
Objective = distance_weight × total_distance
          + thm_weight × opened_THMs
          + floor_weight × active_floors
```

Default weights: `distance=1, thm=15, floor=30`

### Key Concepts

- **THM**: Pick cart/container unit
- **Floor**: Warehouse level (MZN1-MZN6)
- **Node**: Physical location (aisle, column, shelf, side)
- **Route**: Sequence of nodes visited per floor
- **Regret**: Cost difference between best and second-best location choice

## Benchmark Results

**25-item/3-floor** (weights 1/1/1):
1. Saved reference: 491.10
2. Exact (30s): 508.72
3. GRASP: 520.50 (1.4s)
4. Regret: 569.84 (0.2s)
5. Betul: 781.60 (0.1s)

**Full dataset** (weights 1/15/30, 2759 articles):
1. Regret/GRASP: 41,079 (9-19s)
2. Betul: 44,863 (2s)
3. Exact (120s): 93,662 (67% gap remaining)

## Common Parameters

- `--distance-weight`, `--thm-weight`, `--floor-weight`: Objective weights
- `--iterations`: GRASP iterations (default 50)
- `--time-limit`: Time budget in seconds
- `--alpha`: GRASP randomization (0-1, default 0.25)
- `--seed`: Random seed for reproducibility

## Output Files

- **Pick list CSV**: Selected locations with `PICK_ORDER` sequence
- **Alternatives CSV**: All candidate locations considered

## Notes

- GRASP uses first iteration as deterministic "elite seed", then explores with controlled randomization
- Regret heuristic is deterministic and very fast, good baseline
- THM-min solvers may not scale to full dataset
- Exact model requires `--max-route-arcs 1000000` for full dataset
- Simulation app expects specific Excel format (see Simulation/README.md)

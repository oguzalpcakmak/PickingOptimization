## Background

Coding for a course in WHU for graduates: Advanced algorithm design and analysis.

This folder originally contained four heuristic algorithms for a toy Generalized Traveling Salesman Problem:

- Tabu Search
- Simulated Annealing
- Ant Colony System
- Genetic Algorithm

## Warehouse Integration

These algorithms now also work with this repository's warehouse picking data and layout through the root-level runner:

```bash
python gtsp_warehouse_solver.py \
  --algorithm annealing \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --pick-data-output benchmark_outputs/gtsp/annealing_pick.csv \
  --alternative-locations-output benchmark_outputs/gtsp/annealing_alt.csv
```

Run all four algorithms together:

```bash
python gtsp_warehouse_solver.py \
  --algorithm all \
  --orders PickOrder.csv \
  --stock StockData.csv \
  --output-dir benchmark_outputs/gtsp
```

Useful filters:

```bash
--floors MZN1,MZN2,MZN3
--articles 567,577,606,609,699
--max-candidates-per-article 8
```

## Modeling Notes

- GTSP search chooses one primary stock location per demanded article.
- If that primary location cannot satisfy the whole demand, a repair phase fills the remaining quantity from the best remaining warehouse locations.
- Warehouse distances use the same aisle/column layout geometry as the rest of the repo.
- Final CSV exports are written in the same format as the other heuristics in this repository.

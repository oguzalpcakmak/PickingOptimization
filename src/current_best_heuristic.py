"""Current best practical heuristic pipeline.

Default pipeline:
  1. LK seed for one-location articles,
  2. ascending grouped strict insertion with open-THM shortcut,
  3. GRASP-style completion if the runtime cap is reached,
  4. delta-cost route cleanup, defaulting to best-improvement 2-opt.

This file is intentionally a thin orchestration layer so the current best
combination can be run without remembering which benchmark scripts to chain.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence

from heuristic_common import (
    ObjectiveWeights,
    cleanup_solution_routes,
    parse_article_list,
    parse_floor_list,
    print_report,
    write_alternative_locations_csv,
    write_pick_csv,
)
from lk_seed_one_loc_ascending_open_thm_benchmark import solve as solve_lk_seed_combo


def normalize_stock_if_needed(stock_path: Path, output_dir: Path) -> Path:
    with stock_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if "STOCK" in fieldnames:
        return stock_path
    if "STOCK_AMOUNT" not in fieldnames:
        raise ValueError(f"{stock_path} has neither STOCK nor STOCK_AMOUNT column.")

    normalized = output_dir / "normalized_stock.csv"
    normalized.parent.mkdir(parents=True, exist_ok=True)
    output_fields = [
        "THM_ID",
        "ARTICLE_CODE",
        "FLOOR",
        "AISLE",
        "COLUMN",
        "SHELF",
        "LEFT_OR_RIGHT",
        "STOCK",
    ]
    with normalized.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "THM_ID": row.get("THM_ID", ""),
                    "ARTICLE_CODE": row.get("ARTICLE_CODE", ""),
                    "FLOOR": row.get("FLOOR", ""),
                    "AISLE": row.get("AISLE", ""),
                    "COLUMN": row.get("COLUMN", ""),
                    "SHELF": row.get("SHELF", ""),
                    "LEFT_OR_RIGHT": row.get("LEFT_OR_RIGHT") or row.get("RIGHT_OR_LEFT") or "",
                    "STOCK": row.get("STOCK_AMOUNT", ""),
                }
            )
    return normalized


def build_summary(solution, *, orders: Path, stock: Path, stock_used: Path, cleanup_time: float) -> dict[str, object]:
    return {
        "algorithm": solution.algorithm,
        "orders": str(orders),
        "stock": str(stock),
        "stock_used": str(stock_used),
        "objective_value": solution.objective_value,
        "distance": solution.total_distance,
        "floors": solution.total_floors,
        "thms": solution.total_thms,
        "pick_rows": solution.total_picks,
        "visited_nodes": sum(result.visited_nodes for result in solution.floor_results),
        "solve_time": solution.solve_time,
        "cleanup_time": cleanup_time,
        "phase_times": solution.phase_times,
        "notes": solution.notes,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the current best heuristic pipeline.")
    parser.add_argument("--orders", default="data/full/PickOrder.csv")
    parser.add_argument("--stock", default="data/full/StockData.csv")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument("--time-limit", type=float, default=300.0, help="Construction cap in seconds. 0 means unlimited.")
    parser.add_argument("--fallback-on-time-limit", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--fallback-alpha", type=float, default=0.25)
    parser.add_argument("--fallback-article-rcl-size", type=int, default=6)
    parser.add_argument("--fallback-location-rcl-size", type=int, default=5)
    parser.add_argument("--fallback-seed", type=int, default=7)
    parser.add_argument("--cleanup-operator", choices=("none", "2-opt", "swap", "relocate"), default="2-opt")
    parser.add_argument("--cleanup-strategy", choices=("first", "best"), default="best")
    parser.add_argument("--cleanup-passes", type=int, default=3)
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471")
    parser.add_argument("--output", default="outputs/benchmark_outputs/current_best/current_best_pick.csv")
    parser.add_argument(
        "--alternative-locations-output",
        default="outputs/benchmark_outputs/current_best/current_best_alt.csv",
    )
    parser.add_argument("--summary-output", default="outputs/benchmark_outputs/current_best/current_best_summary.json")
    args = parser.parse_args(argv)

    weights = ObjectiveWeights(distance=args.distance_weight, thm=args.thm_weight, floor=args.floor_weight)
    orders = Path(args.orders)
    stock = Path(args.stock)
    summary_output = Path(args.summary_output)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    stock_for_solver = normalize_stock_if_needed(stock, summary_output.parent)

    base_solution, _ = solve_lk_seed_combo(
        orders,
        stock_for_solver,
        distance_weight=weights.distance,
        thm_weight=weights.thm,
        floor_weight=weights.floor,
        time_limit=args.time_limit,
        fallback_on_time_limit=args.fallback_on_time_limit,
        fallback_alpha=args.fallback_alpha,
        fallback_article_rcl_size=args.fallback_article_rcl_size,
        fallback_location_rcl_size=args.fallback_location_rcl_size,
        fallback_seed=args.fallback_seed,
        floors=parse_floor_list(args.floors),
        articles=parse_article_list(args.articles),
    )
    solution, cleanup_time = cleanup_solution_routes(
        base_solution,
        weights=weights,
        operator=args.cleanup_operator,
        strategy=args.cleanup_strategy,
        max_passes=args.cleanup_passes,
    )

    print_report(solution)
    write_pick_csv(solution, args.output)
    write_alternative_locations_csv(solution, args.alternative_locations_output)
    summary = build_summary(
        solution,
        orders=orders,
        stock=stock,
        stock_used=stock_for_solver,
        cleanup_time=cleanup_time,
    )
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nPick output written to {args.output}")
    print(f"Alternative locations written to {args.alternative_locations_output}")
    print(f"Summary written to {summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

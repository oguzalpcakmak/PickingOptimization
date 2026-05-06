"""Comprehensive benchmark runner for the Python v2 flow.

Runs the v2 construction/fallback logic across:
  - old full data, new data, and 4000 sample,
  - 2 minute, 5 minute, and unlimited construction budgets,
  - none, 2-opt, swap, relocate, and the v2 sequence cleanup,
  - first-improvement and best-improvement cleanup strategies.

The v2 solver currently has a fixed final cleanup sequence baked in. This
runner temporarily disables that built-in cleanup while calling ``solve`` so
all cleanup variants can be compared fairly on the same v2 allocation.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import lk_seed_one_loc_ascending_open_thm_benchmark_v2 as v2_solver
from heuristic_common import (
    ObjectiveWeights,
    Solution,
    cleanup_solution_routes,
    load_demands,
    write_alternative_locations_csv,
    write_pick_csv,
)
from real_pick_baselines import get_real_pick_baseline


REPO_ROOT = Path(__file__).resolve().parents[1]

DATASETS = [
    {
        "slug": "old_full_data",
        "label": "Old Full Data",
        "orders": Path("data/full/PickOrder.csv"),
        "stock": Path("data/full/StockData.csv"),
    },
    {
        "slug": "new_data",
        "label": "New Data",
        "orders": Path("data/new_data/OrderData.csv"),
        "stock": Path("data/new_data/StockData.csv"),
    },
    {
        "slug": "4000_sample",
        "label": "4000 Sample",
        "orders": Path("data/4000_sample/PickOrder_sample_4000.csv"),
        "stock": Path("data/4000_sample/StockData.csv"),
    },
]

BUDGETS = [
    {
        "slug": "2min",
        "label": "2 min cap + visited-area fallback",
        "time_limit": 120.0,
        "fallback_on_time_limit": True,
    },
    {
        "slug": "5min",
        "label": "5 min cap + visited-area fallback",
        "time_limit": 300.0,
        "fallback_on_time_limit": True,
    },
    {
        "slug": "unlimited",
        "label": "Unlimited",
        "time_limit": 0.0,
        "fallback_on_time_limit": False,
    },
]

CLEANUPS = [
    ("none", "none"),
    ("two_opt", "2-opt"),
    ("swap", "swap"),
    ("relocate", "relocate"),
    ("v2_sequence", "2-opt -> swap -> relocate"),
]

STRATEGIES = [
    ("first", "first improvement"),
    ("best", "best improvement"),
]

V2_SEQUENCE = ("2-opt", "swap", "relocate")


def _selected(values: list[str]) -> set[str]:
    return {slug.strip() for value in values for slug in value.split(",") if slug.strip()}


def normalize_stock_if_needed(stock_path: Path, output_dir: Path) -> Path:
    with (REPO_ROOT / stock_path).open(newline="", encoding="utf-8-sig") as handle:
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
    return normalized.relative_to(REPO_ROOT)


@contextmanager
def temporarily_disable_v2_builtin_cleanup() -> Iterator[None]:
    original_cleanup = v2_solver.cleanup_solution_routes

    def no_op_cleanup(solution: Solution, **_: Any) -> tuple[Solution, float]:
        return solution, 0.0

    v2_solver.cleanup_solution_routes = no_op_cleanup
    try:
        yield
    finally:
        v2_solver.cleanup_solution_routes = original_cleanup


def solve_v2_construction_base(
    *,
    dataset: dict[str, Any],
    budget: dict[str, Any],
    output_dir: Path,
    weights: ObjectiveWeights,
) -> tuple[Solution, Path]:
    stock_for_solver = normalize_stock_if_needed(Path(dataset["stock"]), output_dir)
    with temporarily_disable_v2_builtin_cleanup():
        solution, _ = v2_solver.solve(
            REPO_ROOT / dataset["orders"],
            REPO_ROOT / stock_for_solver,
            distance_weight=weights.distance,
            thm_weight=weights.thm,
            floor_weight=weights.floor,
            time_limit=budget["time_limit"],
            fallback_on_time_limit=bool(budget["fallback_on_time_limit"]),
        )

    solution.algorithm = "Python v2 construction base"
    solution.notes.update(
        {
            "benchmark_base": "v2 construction/fallback with built-in cleanup disabled",
            "route_cleanup": "disabled before benchmark cleanup variants",
            "sequential_cleanup_time": 0.0,
        }
    )
    return solution, stock_for_solver


def apply_cleanup_variant(
    base_solution: Solution,
    *,
    cleanup_slug: str,
    cleanup_label: str,
    strategy_slug: str,
    weights: ObjectiveWeights,
    max_passes: int,
) -> tuple[Solution, float]:
    if cleanup_slug == "v2_sequence":
        solution = base_solution
        cleanup_total = 0.0
        for operator in V2_SEQUENCE:
            solution, cleanup_time = cleanup_solution_routes(
                solution,
                weights=weights,
                operator=operator,
                strategy=strategy_slug,
                max_passes=max_passes,
            )
            cleanup_total += cleanup_time
        solution.algorithm = f"{base_solution.algorithm} + {cleanup_label} ({strategy_slug})"
        solution.notes.update(
            {
                "route_cleanup": f"{cleanup_label} ({strategy_slug})",
                "route_cleanup_operator": cleanup_slug,
                "route_cleanup_strategy": strategy_slug,
                "route_cleanup_max_passes": max_passes,
                "route_cleanup_time": cleanup_total,
            }
        )
        solution.phase_times["route_cleanup"] = cleanup_total
        solution.phase_times["total"] = solution.solve_time
        return solution, cleanup_total

    solution, cleanup_time = cleanup_solution_routes(
        base_solution,
        weights=weights,
        operator=cleanup_label,
        strategy=strategy_slug,
        max_passes=max_passes,
    )
    return solution, cleanup_time


def int_note(notes: dict[str, Any], key: str) -> int:
    try:
        return int(float(notes.get(key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def run_case(
    *,
    base_solution: Solution,
    stock_for_solver: Path,
    dataset: dict[str, Any],
    budget: dict[str, Any],
    cleanup_slug: str,
    cleanup_label: str,
    strategy_slug: str,
    strategy_label: str,
    output_root: Path,
    weights: ObjectiveWeights,
    max_passes: int,
) -> dict[str, Any]:
    output_dir = output_root / dataset["slug"] / budget["slug"] / cleanup_slug / strategy_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    solution, cleanup_time = apply_cleanup_variant(
        base_solution,
        cleanup_slug=cleanup_slug,
        cleanup_label=cleanup_label,
        strategy_slug=strategy_slug,
        weights=weights,
        max_passes=max_passes,
    )

    pick_output = output_dir / "pick.csv"
    alt_output = output_dir / "alt.csv"
    write_pick_csv(solution, pick_output)
    write_alternative_locations_csv(solution, alt_output)

    notes = solution.notes
    row = {
        "dataset_slug": dataset["slug"],
        "dataset": dataset["label"],
        "orders": str(dataset["orders"]),
        "stock": str(dataset["stock"]),
        "stock_used": str(stock_for_solver),
        "budget_slug": budget["slug"],
        "budget": budget["label"],
        "time_limit": budget["time_limit"],
        "cleanup_slug": cleanup_slug,
        "cleanup": cleanup_label,
        "strategy_slug": strategy_slug,
        "strategy": strategy_label,
        "max_passes": max_passes,
        "objective": solution.objective_value,
        "distance": solution.total_distance,
        "floors": solution.total_floors,
        "thms": solution.total_thms,
        "pick_rows": solution.total_picks,
        "visited_nodes": sum(result.visited_nodes for result in solution.floor_results),
        "solve_time": solution.solve_time,
        "construction_time": base_solution.solve_time,
        "cleanup_time": cleanup_time,
        "timed_out": bool(notes.get("timed_out")),
        "fallback_used": bool(notes.get("fallback_used")),
        "remaining_articles_before_fallback": int_note(notes, "remaining_articles_before_fallback"),
        "remaining_units_before_fallback": int_note(notes, "remaining_units_before_fallback"),
        "strict_steps": int_note(notes, "strict_steps"),
        "strict_candidate_evals": int_note(notes, "strict_candidate_evals"),
        "strict_position_evals": int_note(notes, "strict_position_evals"),
        "fallback_steps": int_note(notes, "fallback_steps"),
        "fallback_visited_box_hits": int_note(notes, "fallback_visited_box_hits"),
        "fallback_visited_half_block_hits": int_note(notes, "fallback_visited_half_block_hits"),
        "fallback_visited_aisle_hits": int_note(notes, "fallback_visited_aisle_hits"),
        "fallback_visited_floor_hits": int_note(notes, "fallback_visited_floor_hits"),
        "fallback_random_hits": int_note(notes, "fallback_random_hits"),
        "pick_output": str(pick_output.relative_to(REPO_ROOT)),
        "alt_output": str(alt_output.relative_to(REPO_ROOT)),
        "summary_output": str((output_dir / "summary.json").relative_to(REPO_ROOT)),
        "solver_summary": {
            "algorithm": solution.algorithm,
            "objective_value": solution.objective_value,
            "distance": solution.total_distance,
            "floors": solution.total_floors,
            "thms": solution.total_thms,
            "pick_rows": solution.total_picks,
            "visited_nodes": sum(result.visited_nodes for result in solution.floor_results),
            "solve_time": solution.solve_time,
            "phase_times": solution.phase_times,
            "notes": solution.notes,
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def validate_pick_outputs(rows: list[dict[str, Any]]) -> None:
    demands_by_orders: dict[str, dict[int, int]] = {}
    for row in rows:
        orders_path = REPO_ROOT / str(row["orders"])
        if str(orders_path) not in demands_by_orders:
            demands_by_orders[str(orders_path)] = load_demands(orders_path)
        demands = demands_by_orders[str(orders_path)]

        picked: dict[int, int] = defaultdict(int)
        with (REPO_ROOT / str(row["pick_output"])).open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for pick_row in reader:
                picked[int(pick_row["ARTICLE_CODE"])] += int(float(pick_row["AMOUNT"]))

        if any(picked.get(article, 0) != qty for article, qty in demands.items()):
            raise ValueError(f"Demand mismatch in {row['pick_output']}")
        if any(article not in demands for article in picked):
            raise ValueError(f"Unexpected picked article in {row['pick_output']}")


def write_report(rows: list[dict[str, Any]], report_path: Path) -> None:
    lines = [
        "# Python V2 Flow Comprehensive Benchmark",
        "",
        "This report benchmarks the Python v2 flow across datasets, runtime budgets, cleanup operators, and first/best improvement strategies.",
        "",
        "V2 construction pipeline: `one-location LK seed + ascending grouped strict insertion + visited-area fallback on timeout`.",
        "",
        "Fairness note: the v2 solver has a fixed built-in final cleanup sequence. This runner temporarily disables that built-in cleanup, then applies each cleanup variant from the same v2 allocation.",
        "",
        "Cleanup variants include the single operators plus the v2 sequence `2-opt -> swap -> relocate`.",
        "",
        f"Cleanup pass limit: `{rows[0]['max_passes'] if rows else 3}` per floor/operator.",
        "",
        "Common objective: `distance + 15 * opened THMs + 30 * active floors`.",
        "",
    ]

    budget_order = [budget["slug"] for budget in BUDGETS]
    cleanup_order = [cleanup[0] for cleanup in CLEANUPS]
    strategy_order = [strategy[0] for strategy in STRATEGIES]
    weights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0)

    for dataset in DATASETS:
        dataset_rows = [row for row in rows if row["dataset_slug"] == dataset["slug"]]
        if not dataset_rows:
            continue
        dataset_rows.sort(
            key=lambda row: (
                budget_order.index(row["budget_slug"]),
                cleanup_order.index(row["cleanup_slug"]),
                strategy_order.index(row["strategy_slug"]),
            )
        )
        real_baseline = get_real_pick_baseline(dataset["slug"], weights=weights)
        lines.extend(
            [
                f"## {dataset['label']}",
                "",
                f"- Orders: `{dataset['orders']}`",
                f"- Stock: `{dataset['stock']}`",
                f"- Solver stock input: `{dataset_rows[0]['stock_used']}`",
                "",
                "| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict evals | Position evals | Construction time | Cleanup time | Total time |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in dataset_rows:
            cap_hit = "Yes" if row["timed_out"] else "No"
            lines.append(
                "| {budget} | {cleanup} | {strategy} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | {cap_hit} | {remaining_units_before_fallback} | {strict_candidate_evals} | {strict_position_evals} | {construction_time:.4f}s | {cleanup_time:.4f}s | {solve_time:.4f}s |".format(
                    **row,
                    cap_hit=cap_hit,
                )
            )
        if real_baseline is not None:
            lines.append(
                "| Real pick baseline | real operation | {method} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | n/a | n/a | n/a | n/a | n/a | n/a | n/a |".format(
                    **real_baseline
                )
            )

        best = min(dataset_rows, key=lambda row: row["objective"])
        fastest = min(dataset_rows, key=lambda row: row["solve_time"])
        lines.extend(
            [
                "",
                f"Best objective: `{best['budget']} + {best['cleanup']} + {best['strategy']}` with `{best['objective']:.2f}`.",
                f"Fastest run: `{fastest['budget']} + {fastest['cleanup']} + {fastest['strategy']}` in `{fastest['solve_time']:.4f}s`.",
            ]
        )
        if real_baseline is not None:
            lines.append(f"Delta vs real-operation baseline: `{best['objective'] - real_baseline['objective']:.2f}` objective points.")
            lines.append(f"Real-operation source: `{real_baseline['source']}`.")
        lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Python v2 flow combinations.")
    parser.add_argument("--output-dir", default="outputs/benchmark_outputs/python_v2_combinations")
    parser.add_argument("--report", default="reports/benchmarks/PYTHON_V2_COMBINATIONS_BENCHMARK.md")
    parser.add_argument("--max-passes", type=int, default=3)
    parser.add_argument("--only-dataset", action="append", default=[], help="Dataset slug(s), repeatable or comma-separated.")
    parser.add_argument("--only-budget", action="append", default=[], help="Budget slug(s), repeatable or comma-separated.")
    parser.add_argument("--only-cleanup", action="append", default=[], help="Cleanup slug(s), repeatable or comma-separated.")
    parser.add_argument("--only-strategy", action="append", default=[], help="Strategy slug(s), repeatable or comma-separated.")
    args = parser.parse_args()

    selected_datasets = _selected(args.only_dataset)
    selected_budgets = _selected(args.only_budget)
    selected_cleanups = _selected(args.only_cleanup)
    selected_strategies = _selected(args.only_strategy)

    known_datasets = {dataset["slug"] for dataset in DATASETS}
    known_budgets = {budget["slug"] for budget in BUDGETS}
    known_cleanups = {cleanup[0] for cleanup in CLEANUPS}
    known_strategies = {strategy[0] for strategy in STRATEGIES}
    if selected_datasets - known_datasets:
        raise ValueError(f"Unknown dataset slug(s): {', '.join(sorted(selected_datasets - known_datasets))}")
    if selected_budgets - known_budgets:
        raise ValueError(f"Unknown budget slug(s): {', '.join(sorted(selected_budgets - known_budgets))}")
    if selected_cleanups - known_cleanups:
        raise ValueError(f"Unknown cleanup slug(s): {', '.join(sorted(selected_cleanups - known_cleanups))}")
    if selected_strategies - known_strategies:
        raise ValueError(f"Unknown strategy slug(s): {', '.join(sorted(selected_strategies - known_strategies))}")

    output_root = REPO_ROOT / args.output_dir
    weights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0)

    rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        if selected_datasets and dataset["slug"] not in selected_datasets:
            continue
        for budget in BUDGETS:
            if selected_budgets and budget["slug"] not in selected_budgets:
                continue
            base_dir = output_root / dataset["slug"] / budget["slug"] / "_base"
            base_dir.mkdir(parents=True, exist_ok=True)
            print(f"Preparing Python v2 base {dataset['slug']} / {budget['slug']} ...", flush=True)
            base_solution, stock_for_solver = solve_v2_construction_base(
                dataset=dataset,
                budget=budget,
                output_dir=base_dir,
                weights=weights,
            )
            for cleanup_slug, cleanup_label in CLEANUPS:
                if selected_cleanups and cleanup_slug not in selected_cleanups:
                    continue
                for strategy_slug, strategy_label in STRATEGIES:
                    if selected_strategies and strategy_slug not in selected_strategies:
                        continue
                    print(
                        f"Running Python v2 {dataset['slug']} / {budget['slug']} / {cleanup_slug} / {strategy_slug} ...",
                        flush=True,
                    )
                    rows.append(
                        run_case(
                            base_solution=base_solution,
                            stock_for_solver=stock_for_solver,
                            dataset=dataset,
                            budget=budget,
                            cleanup_slug=cleanup_slug,
                            cleanup_label=cleanup_label,
                            strategy_slug=strategy_slug,
                            strategy_label=strategy_label,
                            output_root=output_root,
                            weights=weights,
                            max_passes=args.max_passes,
                        )
                    )

    validate_pick_outputs(rows)
    write_report(rows, REPO_ROOT / args.report)
    (output_root / "run_summary.json").write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps({"report": args.report, "rows": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Compare first-improvement vs best-improvement route cleanup.

The allocation/construction outputs come from ``runtime_fallback_benchmark.py``.
For every dataset, runtime budget, and cleanup operator, this script applies two
local-search strategies:
  - first improvement: apply the first improving move found in scan order,
  - best improvement: scan the whole neighborhood and apply the best move.

Both strategies use the same maximum number of accepted moves/passes so the
runtime comparison stays controlled.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, Sequence

from heuristic_common import (
    FloorResult,
    ObjectiveWeights,
    Solution,
    cleanup_route_delta,
    route_cost,
    write_alternative_locations_csv,
    write_pick_csv,
)
from real_pick_baselines import get_real_pick_baseline
from runtime_fallback_benchmark import BUDGETS, DATASETS
from runtime_fallback_cleanup_benchmark import reconstruct_base_solution, resolve_reorganized_path


Route = list[tuple[int, int]]
StrategyCleaner = Callable[[Sequence[tuple[int, int]], str, int], Route]


STRATEGIES = [
    ("first", "first improvement"),
    ("best", "best improvement"),
]


def clean_none(route: Sequence[tuple[int, int]], strategy: str, max_passes: int) -> Route:
    return list(route)


def clean_two_opt(route: Sequence[tuple[int, int]], strategy: str, max_passes: int) -> Route:
    return cleanup_route_delta(route, operator="2-opt", strategy=strategy, max_passes=max_passes)


def clean_swap(route: Sequence[tuple[int, int]], strategy: str, max_passes: int) -> Route:
    return cleanup_route_delta(route, operator="swap", strategy=strategy, max_passes=max_passes)


def clean_relocate(route: Sequence[tuple[int, int]], strategy: str, max_passes: int) -> Route:
    return cleanup_route_delta(route, operator="relocate", strategy=strategy, max_passes=max_passes)


CLEANUP_OPERATORS = [
    ("none", "none", clean_none),
    ("two_opt", "2-opt", clean_two_opt),
    ("swap", "swap", clean_swap),
    ("relocate", "relocate", clean_relocate),
]


def build_cleaned_solution(
    base_solution: Solution,
    *,
    cleanup_slug: str,
    cleanup_label: str,
    strategy_slug: str,
    strategy_label: str,
    cleaner: StrategyCleaner,
    max_passes: int,
    weights: ObjectiveWeights,
) -> tuple[Solution, float]:
    cleanup_start = time.perf_counter()
    floor_results: list[FloorResult] = []
    for floor_result in base_solution.floor_results:
        route = cleaner(floor_result.route, strategy_slug, max_passes)
        floor_results.append(
            FloorResult(
                floor=floor_result.floor,
                picks=dict(floor_result.picks),
                route=route,
                route_distance=route_cost(route),
                opened_thms=set(floor_result.opened_thms),
                visited_nodes=len(route),
            )
        )
    cleanup_time = time.perf_counter() - cleanup_start

    all_thms: set[str] = set()
    for floor_result in floor_results:
        all_thms |= floor_result.opened_thms
    total_distance = sum(result.route_distance for result in floor_results)
    objective = weights.distance * total_distance + weights.thm * len(all_thms) + weights.floor * len(floor_results)

    solution = Solution(
        algorithm=f"{base_solution.algorithm} + {cleanup_label} + {strategy_label}",
        floor_results=floor_results,
        total_distance=total_distance,
        total_thms=len(all_thms),
        total_floors=len(floor_results),
        total_picks=sum(len(result.picks) for result in floor_results),
        solve_time=base_solution.solve_time + cleanup_time,
        phase_times={
            "construction": base_solution.solve_time,
            "route_cleanup": cleanup_time,
            "total": base_solution.solve_time + cleanup_time,
        },
        objective_value=objective,
        demands=dict(base_solution.demands),
        relevant_locs=list(base_solution.relevant_locs),
        loc_lookup=dict(base_solution.loc_lookup),
        notes={
            **base_solution.notes,
            "cleanup": cleanup_label,
            "improvement_strategy": strategy_label,
            "max_passes": max_passes,
        },
    )
    return solution, cleanup_time


def run_case(
    *,
    summary_path: Path,
    output_dir: Path,
    weights: ObjectiveWeights,
    max_passes: int,
) -> list[dict[str, object]]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    base_solution = reconstruct_base_solution(summary, weights)

    rows: list[dict[str, object]] = []
    for cleanup_slug, cleanup_label, cleaner in CLEANUP_OPERATORS:
        for strategy_slug, strategy_label in STRATEGIES:
            variant_dir = output_dir / cleanup_slug / strategy_slug
            variant_dir.mkdir(parents=True, exist_ok=True)
            solution, cleanup_time = build_cleaned_solution(
                base_solution,
                cleanup_slug=cleanup_slug,
                cleanup_label=cleanup_label,
                strategy_slug=strategy_slug,
                strategy_label=strategy_label,
                cleaner=cleaner,
                max_passes=max_passes,
                weights=weights,
            )
            pick_output = variant_dir / "pick.csv"
            alt_output = variant_dir / "alt.csv"
            write_pick_csv(solution, pick_output)
            write_alternative_locations_csv(solution, alt_output)

            row = {
                **{key: value for key, value in summary.items() if key != "solver_summary"},
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
                "construction_time": base_solution.solve_time,
                "cleanup_time": cleanup_time,
                "solve_time": solution.solve_time,
                "pick_output": str(pick_output),
                "alt_output": str(alt_output),
            }
            (variant_dir / "summary.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            rows.append(row)
    return rows


def write_report(rows: list[dict[str, object]], report_path: Path) -> None:
    lines = [
        "# First vs Best Improvement Cleanup Benchmark",
        "",
        "This report compares first-improvement and best-improvement local search on top of the runtime fallback benchmark outputs.",
        "",
        "Allocation is fixed within each runtime setting. Only the final route cleanup strategy changes.",
        "",
        "Definition used here: first improvement applies the first improving move found in scan order; best improvement scans the full neighborhood and applies the best improving move.",
        "",
        f"Both strategies are limited to `{rows[0]['max_passes'] if rows else 3}` accepted moves/passes per floor to match the previous cleanup benchmark scale.",
        "",
        "Note: this is a pure first-vs-best comparison. The earlier cleanup benchmark used a greedy pass that updated the route immediately while continuing the scan, so its numbers are not expected to match this table exactly.",
        "",
        "Common objective: `distance + 15 * opened THMs + 30 * active floors`.",
        "",
    ]

    dataset_order = [dataset["slug"] for dataset in DATASETS]
    budget_order = [budget["slug"] for budget in BUDGETS]
    cleanup_order = [cleanup[0] for cleanup in CLEANUP_OPERATORS]
    strategy_order = [strategy[0] for strategy in STRATEGIES]

    for dataset in DATASETS:
        dataset_rows = [row for row in rows if row["dataset_slug"] == dataset["slug"]]
        if not dataset_rows:
            continue
        real_baseline = get_real_pick_baseline(str(dataset["slug"]))
        dataset_rows.sort(
            key=lambda row: (
                budget_order.index(row["budget_slug"]),
                cleanup_order.index(row["cleanup_slug"]),
                strategy_order.index(row["strategy_slug"]),
            )
        )
        lines.extend(
            [
                f"## {dataset['label']}",
                "",
                f"- Orders: `{dataset_rows[0]['orders']}`",
                f"- Stock: `{dataset_rows[0]['stock']}`",
                f"- Solver stock input: `{dataset_rows[0]['stock_used']}`",
                "",
                "| Runtime setting | Cleanup | Strategy | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|",
            ]
        )
        for row in dataset_rows:
            values = dict(row)
            values["cap_hit"] = "Yes" if row["timed_out"] else "No"
            lines.append(
                "| {budget} | {cleanup} | {strategy} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | {cap_hit} | {remaining_units_before_fallback} | {construction_time:.2f}s | {cleanup_time:.2f}s | {solve_time:.2f}s |".format(
                    **values
                )
            )
        if real_baseline is not None:
            lines.append(
                "| Real pick baseline | real operation | {method} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | n/a | n/a | n/a | n/a | n/a |".format(
                    **real_baseline
                )
            )

        best = min(dataset_rows, key=lambda row: row["objective"])
        lines.extend(
            [
                "",
                f"Best objective in this dataset: `{best['budget']} + {best['cleanup']} + {best['strategy']}` with `{best['objective']:.2f}`.",
            ]
        )
        if real_baseline is not None:
            lines.append(
                f"Delta vs real-operation baseline: `{best['objective'] - real_baseline['objective']:.2f}` objective points."
            )
            lines.append(f"Real-operation source: `{real_baseline['source']}`.")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def _selected(values: list[str]) -> set[str]:
    return {slug.strip() for value in values for slug in value.split(",") if slug.strip()}


def validate_pick_outputs(rows: list[dict[str, object]]) -> None:
    demands_by_orders: dict[str, dict[int, int]] = {}
    for row in rows:
        orders = str(resolve_reorganized_path(row["orders"]))
        if orders not in demands_by_orders:
            from heuristic_common import load_demands

            demands_by_orders[orders] = load_demands(orders)
        demands = demands_by_orders[orders]
        picked: dict[int, int] = defaultdict(int)
        with Path(row["pick_output"]).open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for pick_row in reader:
                picked[int(pick_row["ARTICLE_CODE"])] += int(float(pick_row["AMOUNT"]))
        if any(picked.get(article, 0) != qty for article, qty in demands.items()):
            raise ValueError(f"Demand mismatch in {row['pick_output']}")
        if any(article not in demands for article in picked):
            raise ValueError(f"Unexpected picked article in {row['pick_output']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare first vs best improvement cleanup strategies.")
    parser.add_argument("--input-dir", default="outputs/benchmark_outputs/runtime_fallback")
    parser.add_argument("--output-dir", default="outputs/benchmark_outputs/runtime_fallback_improvement_strategy")
    parser.add_argument("--report", default="reports/benchmarks/RUNTIME_FALLBACK_IMPROVEMENT_STRATEGY_BENCHMARK.md")
    parser.add_argument("--max-passes", type=int, default=3)
    parser.add_argument("--only-dataset", action="append", default=[], help="Dataset slug(s), repeatable or comma-separated.")
    parser.add_argument("--only-budget", action="append", default=[], help="Budget slug(s), repeatable or comma-separated.")
    args = parser.parse_args(argv)

    selected_datasets = _selected(args.only_dataset)
    selected_budgets = _selected(args.only_budget)
    known_datasets = {dataset["slug"] for dataset in DATASETS}
    known_budgets = {budget["slug"] for budget in BUDGETS}
    if selected_datasets - known_datasets:
        raise ValueError(f"Unknown dataset slug(s): {', '.join(sorted(selected_datasets - known_datasets))}")
    if selected_budgets - known_budgets:
        raise ValueError(f"Unknown budget slug(s): {', '.join(sorted(selected_budgets - known_budgets))}")

    input_root = Path(args.input_dir)
    output_root = Path(args.output_dir)
    weights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0)

    rows: list[dict[str, object]] = []
    for dataset in DATASETS:
        if selected_datasets and dataset["slug"] not in selected_datasets:
            continue
        for budget in BUDGETS:
            if selected_budgets and budget["slug"] not in selected_budgets:
                continue
            summary_path = input_root / dataset["slug"] / budget["slug"] / "summary.json"
            if not summary_path.exists():
                raise FileNotFoundError(f"Missing base summary: {summary_path}")
            print(f"Comparing {dataset['slug']} / {budget['slug']} ...", flush=True)
            rows.extend(
                run_case(
                    summary_path=summary_path,
                    output_dir=output_root / dataset["slug"] / budget["slug"],
                    weights=weights,
                    max_passes=args.max_passes,
                )
            )

    write_report(rows, Path(args.report))
    validate_pick_outputs(rows)
    print(
        json.dumps(
            {
                "report": args.report,
                "rows": [
                    {
                        "dataset": row["dataset"],
                        "budget": row["budget"],
                        "cleanup": row["cleanup"],
                        "strategy": row["strategy"],
                        "objective": row["objective"],
                        "distance": row["distance"],
                        "thms": row["thms"],
                        "solve_time": row["solve_time"],
                    }
                    for row in rows
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

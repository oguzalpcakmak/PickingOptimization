"""Apply route cleanup variants to runtime fallback benchmark outputs.

This script reuses existing outputs from ``runtime_fallback_benchmark.py`` and
does not rerun allocation/construction. It reconstructs each solution from the
written alternative-location CSV, then applies:
  - none,
  - 2-opt,
  - swap,
  - relocate.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from heuristic_common import (
    FloorResult,
    ObjectiveWeights,
    Solution,
    cleanup_solution_routes,
    floor_index,
    prepare_problem,
    route_cost,
    write_alternative_locations_csv,
    write_pick_csv,
)
from real_pick_baselines import get_real_pick_baseline
from runtime_fallback_benchmark import BUDGETS, DATASETS


CLEANERS: dict[str, tuple[str, str]] = {
    "none": ("none", "none"),
    "two_opt": ("2-opt", "2-opt"),
    "swap": ("swap", "swap"),
    "relocate": ("relocate", "relocate"),
}


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def resolve_reorganized_path(value: object) -> Path:
    """Resolve paths stored before the repo was reorganized."""

    text = str(value)
    path = Path(text)
    if path.exists():
        return path

    exact_rewrites = {
        "PickOrder.csv": "data/full/PickOrder.csv",
        "StockData.csv": "data/full/StockData.csv",
    }
    if text in exact_rewrites:
        rewritten = Path(exact_rewrites[text])
        if rewritten.exists():
            return rewritten

    prefix_rewrites = (
        ("NEW_DATA/", "data/new_data/"),
        ("4000SAMPLE/", "data/4000_sample/"),
        ("25item3floor/", "data/25item3floor/"),
        ("benchmark_outputs/", "outputs/benchmark_outputs/"),
    )
    for old_prefix, new_prefix in prefix_rewrites:
        if text.startswith(old_prefix):
            rewritten = Path(new_prefix + text[len(old_prefix) :])
            if rewritten.exists():
                return rewritten

    return path


def reconstruct_base_solution(summary: dict[str, object], weights: ObjectiveWeights) -> Solution:
    orders_path = resolve_reorganized_path(summary["orders"])
    stock_path = resolve_reorganized_path(summary["stock_used"])
    demands, relevant_locs, loc_lookup, _ = prepare_problem(orders_path, stock_path)

    picks_by_location: dict[str, int] = {}
    route_order_by_floor: dict[str, dict[tuple[int, int], int]] = defaultdict(dict)
    with resolve_reorganized_path(summary["alt_output"]).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lid = str(row["LOCATION_ID"])
            picked_amount = int(float(row.get("PICKED_AMOUNT") or 0))
            if picked_amount > 0:
                picks_by_location[lid] = picked_amount

            pick_order_text = str(row.get("PICK_ORDER") or "").strip()
            if _truthy(row.get("NODE_VISITED")) and pick_order_text:
                floor = str(row["FLOOR"]).strip().upper()
                node = (int(row["AISLE"]), int(row["COLUMN"]))
                pick_order = int(float(pick_order_text))
                current = route_order_by_floor[floor].get(node)
                if current is None or pick_order < current:
                    route_order_by_floor[floor][node] = pick_order

    picks_by_floor: dict[str, dict[str, int]] = defaultdict(dict)
    active_nodes_by_floor: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for lid, qty in picks_by_location.items():
        loc = loc_lookup[lid]
        picks_by_floor[loc.floor][lid] = qty
        active_nodes_by_floor[loc.floor].add(loc.node2d)

    floor_results: list[FloorResult] = []
    for floor in sorted(picks_by_floor, key=floor_index):
        ordered_nodes = [
            node
            for node, _ in sorted(
                route_order_by_floor[floor].items(),
                key=lambda item: (item[1], item[0][0], item[0][1]),
            )
        ]
        missing_nodes = sorted(active_nodes_by_floor[floor] - set(ordered_nodes))
        route = ordered_nodes + missing_nodes
        opened_thms = {loc_lookup[lid].thm_id for lid in picks_by_floor[floor]}
        floor_results.append(
            FloorResult(
                floor=floor,
                picks=dict(picks_by_floor[floor]),
                route=route,
                route_distance=route_cost(route),
                opened_thms=opened_thms,
                visited_nodes=len(route),
            )
        )

    all_thms: set[str] = set()
    for floor_result in floor_results:
        all_thms |= floor_result.opened_thms
    total_distance = sum(floor_result.route_distance for floor_result in floor_results)
    objective = weights.distance * total_distance + weights.thm * len(all_thms) + weights.floor * len(floor_results)

    return Solution(
        algorithm="Runtime fallback base reconstructed from benchmark outputs",
        floor_results=floor_results,
        total_distance=total_distance,
        total_thms=len(all_thms),
        total_floors=len(floor_results),
        total_picks=sum(len(result.picks) for result in floor_results),
        solve_time=float(summary["solve_time"]),
        phase_times={"construction": float(summary["solve_time"])},
        objective_value=objective,
        demands=demands,
        relevant_locs=relevant_locs,
        loc_lookup=loc_lookup,
        notes=dict(summary),
    )


def build_cleaned_solution(
    base_solution: Solution,
    *,
    variant_name: str,
    cleaner_label: str,
    cleaner_operator: str,
    weights: ObjectiveWeights,
) -> tuple[Solution, float]:
    solution, cleanup_time = cleanup_solution_routes(
        base_solution,
        weights=weights,
        operator=cleaner_operator,
        strategy="best",
        max_passes=3,
    )
    solution.algorithm = variant_name
    solution.notes["route_cleanup"] = cleaner_label
    return solution, cleanup_time


def run_case(
    *,
    summary_path: Path,
    output_dir: Path,
    weights: ObjectiveWeights,
) -> list[dict[str, object]]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    base_solution = reconstruct_base_solution(summary, weights)

    rows = []
    for cleaner_slug, (cleaner_label, cleaner_operator) in CLEANERS.items():
        variant_dir = output_dir / cleaner_slug
        variant_dir.mkdir(parents=True, exist_ok=True)
        solution, cleanup_time = build_cleaned_solution(
            base_solution,
            variant_name=f"{base_solution.algorithm} + {cleaner_label}",
            cleaner_label=cleaner_label,
            cleaner_operator=cleaner_operator,
            weights=weights,
        )
        pick_output = variant_dir / "pick.csv"
        alt_output = variant_dir / "alt.csv"
        write_pick_csv(solution, pick_output)
        write_alternative_locations_csv(solution, alt_output)

        row = {
            **{key: value for key, value in summary.items() if key != "solver_summary"},
            "cleanup_slug": cleaner_slug,
            "cleanup": cleaner_label,
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
        "# Runtime Cap + Route Cleanup Benchmark",
        "",
        "This report starts from the runtime-capped strict insertion + GRASP fallback outputs, then applies final route cleanup variants.",
        "",
        "Allocation is fixed within each runtime setting; only the final route order changes between `none`, `2-opt`, `swap`, and `relocate`.",
        "",
        "Common objective: `distance + 15 * opened THMs + 30 * active floors`.",
        "",
    ]

    dataset_order = [dataset["slug"] for dataset in DATASETS]
    budget_order = [budget["slug"] for budget in BUDGETS]
    cleanup_order = list(CLEANERS)

    for dataset in DATASETS:
        dataset_rows = [row for row in rows if row["dataset_slug"] == dataset["slug"]]
        if not dataset_rows:
            continue
        real_baseline = get_real_pick_baseline(str(dataset["slug"]))
        dataset_rows.sort(key=lambda row: (budget_order.index(row["budget_slug"]), cleanup_order.index(row["cleanup_slug"])))
        lines.extend(
            [
                f"## {dataset['label']}",
                "",
                f"- Orders: `{dataset_rows[0]['orders']}`",
                f"- Stock: `{dataset_rows[0]['stock']}`",
                f"- Solver stock input: `{dataset_rows[0]['stock_used']}`",
                "",
                "| Runtime setting | Cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Construction time | Cleanup time | Total time |",
                "|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|",
            ]
        )
        for row in dataset_rows:
            values = dict(row)
            values["cap_hit"] = "Yes" if row["timed_out"] else "No"
            lines.append(
                "| {budget} | {cleanup} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | {cap_hit} | {remaining_units_before_fallback} | {construction_time:.2f}s | {cleanup_time:.2f}s | {solve_time:.2f}s |".format(
                    **values
                )
            )
        if real_baseline is not None:
            lines.append(
                "| Real pick baseline | {method} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | n/a | n/a | n/a | n/a | n/a |".format(
                    **real_baseline
                )
            )
        best = min(dataset_rows, key=lambda row: row["objective"])
        lines.extend(
            [
                "",
                f"Best objective in this dataset: `{best['budget']} + {best['cleanup']}` with `{best['objective']:.2f}`.",
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply route cleanup variants to runtime fallback benchmark outputs.")
    parser.add_argument("--input-dir", default="outputs/benchmark_outputs/runtime_fallback")
    parser.add_argument("--output-dir", default="outputs/benchmark_outputs/runtime_fallback_cleanup")
    parser.add_argument("--report", default="reports/benchmarks/RUNTIME_FALLBACK_CLEANUP_BENCHMARK.md")
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

    rows = []
    for dataset in DATASETS:
        if selected_datasets and dataset["slug"] not in selected_datasets:
            continue
        for budget in BUDGETS:
            if selected_budgets and budget["slug"] not in selected_budgets:
                continue
            summary_path = input_root / dataset["slug"] / budget["slug"] / "summary.json"
            if not summary_path.exists():
                raise FileNotFoundError(f"Missing base summary: {summary_path}")
            print(f"Cleaning {dataset['slug']} / {budget['slug']} ...", flush=True)
            rows.extend(
                run_case(
                    summary_path=summary_path,
                    output_dir=output_root / dataset["slug"] / budget["slug"],
                    weights=weights,
                )
            )

    write_report(rows, Path(args.report))
    print(
        json.dumps(
            {
                "report": args.report,
                "rows": [
                    {
                        "dataset": row["dataset"],
                        "budget": row["budget"],
                        "cleanup": row["cleanup"],
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

"""Benchmark route cleanup variants on the LK-seeded grouped heuristic.

The allocation/backbone combination is kept fixed per dataset:
  1. commit one-location articles,
  2. build an LK seed route for those picks,
  3. process remaining articles by ascending candidate-count groups,
  4. prefer already-open THMs, otherwise use strict insertion.

Only the final per-floor route cleanup changes between variants.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Sequence

from heuristic_common import (
    ObjectiveWeights,
    Solution,
    cleanup_solution_routes,
    write_alternative_locations_csv,
    write_pick_csv,
)
from lk_seed_one_loc_ascending_open_thm_benchmark import solve as solve_lk_seed_combo
from real_pick_baselines import get_real_pick_baseline


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

CLEANERS: dict[str, tuple[str, str]] = {
    "none": ("none", "none"),
    "two_opt": ("2-opt", "2-opt"),
    "swap": ("swap", "swap"),
    "relocate": ("relocate", "relocate"),
}


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


def _normalized_repo_path(value: object) -> str:
    text = str(value)
    exact_rewrites = {
        "PickOrder.csv": "data/full/PickOrder.csv",
        "StockData.csv": "data/full/StockData.csv",
    }
    if text in exact_rewrites:
        return exact_rewrites[text]
    prefix_rewrites = (
        ("NEW_DATA/", "data/new_data/"),
        ("4000SAMPLE/", "data/4000_sample/"),
        ("benchmark_outputs/", "outputs/benchmark_outputs/"),
    )
    for old_prefix, new_prefix in prefix_rewrites:
        if text.startswith(old_prefix):
            return new_prefix + text[len(old_prefix) :]
    return text


def _report_link(value: object, report_path: Path) -> str:
    normalized = _normalized_repo_path(value)
    return os.path.relpath(normalized, start=report_path.parent)


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
    solution.notes["base_algorithm"] = base_solution.algorithm
    solution.notes["route_cleanup"] = cleaner_label
    return solution, cleanup_time


def run_dataset(
    *,
    label: str,
    orders: Path,
    stock: Path,
    output_dir: Path,
    weights: ObjectiveWeights,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stock_for_solver = normalize_stock_if_needed(stock, output_dir)

    base_solution, base_summary = solve_lk_seed_combo(
        orders,
        stock_for_solver,
        distance_weight=weights.distance,
        thm_weight=weights.thm,
        floor_weight=weights.floor,
    )

    variants = []
    for slug, (cleaner_label, cleaner_operator) in CLEANERS.items():
        solution, cleanup_time = build_cleaned_solution(
            base_solution,
            variant_name=f"{base_solution.algorithm} + {cleaner_label}",
            cleaner_label=cleaner_label,
            cleaner_operator=cleaner_operator,
            weights=weights,
        )
        pick_output = output_dir / f"{slug}_pick.csv"
        alt_output = output_dir / f"{slug}_alt.csv"
        write_pick_csv(solution, pick_output)
        write_alternative_locations_csv(solution, alt_output)
        variants.append(
            {
                "variant": cleaner_label,
                "objective": solution.objective_value,
                "distance": solution.total_distance,
                "floors": solution.total_floors,
                "thms": solution.total_thms,
                "pick_rows": solution.total_picks,
                "visited_nodes": sum(result.visited_nodes for result in solution.floor_results),
                "base_time": base_solution.solve_time,
                "cleanup_time": cleanup_time,
                "total_time": solution.solve_time,
                "pick_output": str(pick_output),
                "alt_output": str(alt_output),
            }
        )

    summary = {
        "dataset": label,
        "orders": str(orders),
        "stock": str(stock),
        "stock_used": str(stock_for_solver),
        "base_summary": base_summary,
        "variants": variants,
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def write_markdown_report(summaries: list[dict[str, object]], report_path: Path) -> None:
    lines = [
        "# Route Cleanup Benchmark: 2-opt vs Swap vs Relocate",
        "",
        "This report keeps the same allocation/backbone combination fixed and compares only the final route cleanup step.",
        "",
        "Base combination: `LK seed for 1-location articles + ascending grouped insertion + open THM shortcut`.",
        "",
        "Common objective: `distance + 15 * opened THMs + 30 * active floors`.",
        "",
    ]

    for summary in summaries:
        label = summary["dataset"]
        dataset_slug = next(
            (dataset["slug"] for dataset in DATASETS if dataset["label"] == label),
            None,
        )
        real_baseline = get_real_pick_baseline(str(dataset_slug)) if dataset_slug else None
        lines.extend(
            [
                f"## {label}",
                "",
                f"- Orders: `{_normalized_repo_path(summary['orders'])}`",
                f"- Stock: `{_normalized_repo_path(summary['stock'])}`",
                f"- Solver stock input: `{_normalized_repo_path(summary['stock_used'])}`",
                "",
                "| Route cleanup | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Base time | Cleanup time | Total time |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        variants = sorted(summary["variants"], key=lambda row: row["objective"])
        for row in variants:
            lines.append(
                "| {variant} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | {base_time:.2f}s | {cleanup_time:.2f}s | {total_time:.2f}s |".format(
                    **row
                )
            )
        if real_baseline is not None:
            lines.append(
                "| {label} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | n/a | n/a | n/a |".format(
                    **real_baseline
                )
            )

        best = variants[0]
        baseline = next(row for row in summary["variants"] if row["variant"] == "none")
        lines.extend(
            [
                "",
                f"Best cleanup: `{best['variant']}` with objective `{best['objective']:.2f}`.",
                f"Delta vs no cleanup: `{best['objective'] - baseline['objective']:.2f}` objective points.",
            ]
        )
        if real_baseline is not None:
            lines.append(
                f"Delta vs real-operation baseline: `{best['objective'] - real_baseline['objective']:.2f}` objective points."
            )
            lines.append(f"Real-operation source: `{real_baseline['source']}`.")
        lines.extend(["", "Artifacts:"])
        for row in variants:
            lines.append(
                f"- `{row['variant']}` pick output: [{Path(row['pick_output']).name}]({_report_link(row['pick_output'], report_path)})"
            )
            lines.append(
                f"- `{row['variant']}` alternatives: [{Path(row['alt_output']).name}]({_report_link(row['alt_output'], report_path)})"
            )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark 2-opt, swap, and relocate route cleanups.")
    parser.add_argument("--output-dir", default="outputs/benchmark_outputs/route_cleanup_comparison")
    parser.add_argument("--report", default="reports/benchmarks/ROUTE_CLEANUP_BENCHMARK_COMPARISON.md")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Dataset slug(s) to run. Can be repeated or comma-separated. Existing summaries for other datasets are reused.",
    )
    args = parser.parse_args(argv)

    output_root = Path(args.output_dir)
    weights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0)

    selected_slugs = {
        slug.strip()
        for only_arg in args.only
        for slug in only_arg.split(",")
        if slug.strip()
    }
    known_slugs = {dataset["slug"] for dataset in DATASETS}
    unknown_slugs = selected_slugs - known_slugs
    if unknown_slugs:
        raise ValueError(f"Unknown dataset slug(s): {', '.join(sorted(unknown_slugs))}. Known: {', '.join(sorted(known_slugs))}")

    summaries = []
    for dataset in DATASETS:
        output_dir = output_root / dataset["slug"]
        should_run = not selected_slugs or dataset["slug"] in selected_slugs
        summary_path = output_dir / "run_summary.json"
        if should_run:
            summary = run_dataset(
                label=dataset["label"],
                orders=dataset["orders"],
                stock=dataset["stock"],
                output_dir=output_dir,
                weights=weights,
            )
        elif summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            continue
        summaries.append(summary)

    write_markdown_report(summaries, Path(args.report))
    print(json.dumps({"report": args.report, "datasets": summaries}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

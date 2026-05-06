"""Benchmark runtime-capped strict insertion with GRASP-style fallback.

Datasets:
  - old full data,
  - new data,
  - 4000 sample.

Budgets:
  - 2 minutes,
  - 5 minutes,
  - unlimited.

If a capped run reaches its limit, the partial LK-seeded grouped-insertion
solution is kept and the remaining demand is completed with GRASP-style RCL
choices on top of the current state.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence

from heuristic_common import ObjectiveWeights, write_alternative_locations_csv, write_pick_csv
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

BUDGETS = [
    {
        "slug": "2min",
        "label": "2 min cap + GRASP fallback",
        "time_limit": 120.0,
        "fallback_on_time_limit": True,
    },
    {
        "slug": "5min",
        "label": "5 min cap + GRASP fallback",
        "time_limit": 300.0,
        "fallback_on_time_limit": True,
    },
    {
        "slug": "unlimited",
        "label": "Unlimited",
        "time_limit": None,
        "fallback_on_time_limit": False,
    },
]


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


def run_case(
    *,
    dataset: dict[str, object],
    budget: dict[str, object],
    output_root: Path,
    weights: ObjectiveWeights,
) -> dict[str, object]:
    output_dir = output_root / str(dataset["slug"]) / str(budget["slug"])
    output_dir.mkdir(parents=True, exist_ok=True)
    stock_for_solver = normalize_stock_if_needed(Path(dataset["stock"]), output_dir)

    solution, solver_summary = solve_lk_seed_combo(
        Path(dataset["orders"]),
        stock_for_solver,
        distance_weight=weights.distance,
        thm_weight=weights.thm,
        floor_weight=weights.floor,
        time_limit=budget["time_limit"],
        fallback_on_time_limit=bool(budget["fallback_on_time_limit"]),
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
        "objective": solution.objective_value,
        "distance": solution.total_distance,
        "floors": solution.total_floors,
        "thms": solution.total_thms,
        "pick_rows": solution.total_picks,
        "visited_nodes": sum(result.visited_nodes for result in solution.floor_results),
        "solve_time": solution.solve_time,
        "timed_out": bool(notes.get("timed_out")),
        "fallback_used": bool(notes.get("fallback_used")),
        "remaining_articles_before_fallback": int(notes.get("remaining_articles_before_fallback", 0)),
        "remaining_units_before_fallback": int(notes.get("remaining_units_before_fallback", 0)),
        "strict_steps": int(notes.get("strict_steps", 0)),
        "strict_candidate_evals": int(notes.get("strict_candidate_evals", 0)),
        "strict_position_evals": int(notes.get("strict_position_evals", 0)),
        "fallback_articles": int(notes.get("fallback_articles", 0)),
        "fallback_steps": int(notes.get("fallback_steps", 0)),
        "fallback_candidate_evals": int(notes.get("fallback_candidate_evals", 0)),
        "timeout_group": notes.get("timeout_group"),
        "timeout_article": notes.get("timeout_article"),
        "pick_output": str(pick_output),
        "alt_output": str(alt_output),
        "solver_summary": solver_summary,
    }
    (output_dir / "summary.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def write_report(rows: list[dict[str, object]], report_path: Path) -> None:
    lines = [
        "# Runtime Cap Benchmark: Strict Insertion + GRASP Fallback",
        "",
        "This report compares the same base combination under 2 minute, 5 minute, and unlimited runtime settings.",
        "",
        "Base combination: `LK seed for 1-location articles + ascending grouped insertion + open THM shortcut`.",
        "",
        "If a cap is reached, the partial solution is kept and remaining demand is completed with GRASP-style RCL choices.",
        "",
        "Final route cleanup is disabled here, so the table isolates construction/fallback behavior.",
        "",
        "Note: these are single-run measurements. The LK seed route can vary slightly between independent runs, so unlimited runs do not always dominate a capped run when the cap is not binding.",
        "",
        "Common objective: `distance + 15 * opened THMs + 30 * active floors`.",
        "",
    ]

    dataset_order = [dataset["slug"] for dataset in DATASETS]
    budget_order = [budget["slug"] for budget in BUDGETS]
    rows_by_dataset = {
        slug: [row for row in rows if row["dataset_slug"] == slug]
        for slug in dataset_order
    }

    for dataset in DATASETS:
        dataset_rows = sorted(
            rows_by_dataset[dataset["slug"]],
            key=lambda row: budget_order.index(row["budget_slug"]),
        )
        if not dataset_rows:
            continue
        real_baseline = get_real_pick_baseline(str(dataset["slug"]))
        lines.extend(
            [
                f"## {dataset['label']}",
                "",
                f"- Orders: `{dataset_rows[0]['orders']}`",
                f"- Stock: `{dataset_rows[0]['stock']}`",
                f"- Solver stock input: `{dataset_rows[0]['stock_used']}`",
                "",
                "| Runtime setting | Objective | Distance | Floors | THMs | Pick rows | Visited nodes | Cap hit? | Fallback articles | Fallback units | Strict steps | Fallback steps | Solve time |",
                "|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in dataset_rows:
            values = dict(row)
            values["cap_hit"] = "Yes" if row["timed_out"] else "No"
            lines.append(
                "| {budget} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | {cap_hit} | {fallback_articles} | {remaining_units_before_fallback} | {strict_steps} | {fallback_steps} | {solve_time:.2f}s |".format(
                    **values
                )
            )
        if real_baseline is not None:
            lines.append(
                "| {label} | {objective:.2f} | {distance:.2f} | {floors} | {thms} | {pick_rows} | {visited_nodes} | n/a | n/a | n/a | n/a | n/a | n/a |".format(
                    **real_baseline
                )
            )

        best = min(dataset_rows, key=lambda row: row["objective"])
        lines.extend(
            [
                "",
                f"Best objective in this dataset: `{best['budget']}` with `{best['objective']:.2f}`.",
            ]
        )
        if real_baseline is not None:
            lines.append(
                f"Delta vs real-operation baseline: `{best['objective'] - real_baseline['objective']:.2f}` objective points."
            )
            lines.append(f"Real-operation source: `{real_baseline['source']}`.")
        lines.extend(["", "Artifacts:"])
        for row in dataset_rows:
            lines.append(f"- `{row['budget']}` pick output: [{Path(row['pick_output']).name}](./{row['pick_output']})")
            lines.append(f"- `{row['budget']}` alternatives: [{Path(row['alt_output']).name}](./{row['alt_output']})")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark runtime-capped strict insertion with GRASP fallback.")
    parser.add_argument("--output-dir", default="outputs/benchmark_outputs/runtime_fallback")
    parser.add_argument("--report", default="reports/benchmarks/RUNTIME_FALLBACK_BENCHMARK.md")
    parser.add_argument("--only-dataset", action="append", default=[], help="Dataset slug(s), repeatable or comma-separated.")
    parser.add_argument("--only-budget", action="append", default=[], help="Budget slug(s), repeatable or comma-separated.")
    args = parser.parse_args(argv)

    selected_datasets = {
        slug.strip()
        for value in args.only_dataset
        for slug in value.split(",")
        if slug.strip()
    }
    selected_budgets = {
        slug.strip()
        for value in args.only_budget
        for slug in value.split(",")
        if slug.strip()
    }
    known_datasets = {dataset["slug"] for dataset in DATASETS}
    known_budgets = {budget["slug"] for budget in BUDGETS}
    if selected_datasets - known_datasets:
        raise ValueError(f"Unknown dataset slug(s): {', '.join(sorted(selected_datasets - known_datasets))}")
    if selected_budgets - known_budgets:
        raise ValueError(f"Unknown budget slug(s): {', '.join(sorted(selected_budgets - known_budgets))}")

    output_root = Path(args.output_dir)
    weights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0)
    rows = []
    for dataset in DATASETS:
        if selected_datasets and dataset["slug"] not in selected_datasets:
            continue
        for budget in BUDGETS:
            if selected_budgets and budget["slug"] not in selected_budgets:
                continue
            print(f"Running {dataset['slug']} / {budget['slug']} ...", flush=True)
            rows.append(run_case(dataset=dataset, budget=budget, output_root=output_root, weights=weights))

    write_report(rows, Path(args.report))
    print(
        json.dumps(
            {
                "report": args.report,
                "rows": [
                    {
                        "dataset": row["dataset"],
                        "budget": row["budget"],
                        "objective": row["objective"],
                        "distance": row["distance"],
                        "thms": row["thms"],
                        "timed_out": row["timed_out"],
                        "fallback_used": row["fallback_used"],
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

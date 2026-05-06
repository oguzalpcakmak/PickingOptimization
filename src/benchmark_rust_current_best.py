"""Comprehensive benchmark runner for the Rust current-best solver.

Runs the pure-Rust implementation across:
  - old full data, new data, and 4000 sample,
  - 2 minute, 5 minute, and unlimited construction budgets,
  - none, 2-opt, swap, and relocate cleanup operators,
  - first-improvement and best-improvement cleanup strategies.

The Rust solver is intentionally benchmarked in its own report because it uses
a pure-Rust seed route instead of Python's external LK package.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from heuristic_common import ObjectiveWeights, load_demands
from real_pick_baselines import get_real_pick_baseline


REPO_ROOT = Path(__file__).resolve().parents[1]
RUST_DIR = REPO_ROOT / "rust_solver"

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
    {"slug": "2min", "label": "2 min cap + GRASP fallback", "time_limit": 120.0},
    {"slug": "5min", "label": "5 min cap + GRASP fallback", "time_limit": 300.0},
    {"slug": "unlimited", "label": "Unlimited", "time_limit": 0.0},
]

CLEANUPS = [
    ("none", "none"),
    ("two_opt", "2-opt"),
    ("swap", "swap"),
    ("relocate", "relocate"),
]

STRATEGIES = [
    ("first", "first improvement"),
    ("best", "best improvement"),
]


def _selected(values: list[str]) -> set[str]:
    return {slug.strip() for value in values for slug in value.split(",") if slug.strip()}


def rust_binary_path() -> Path:
    suffix = ".exe" if sys.platform.startswith("win") else ""
    return RUST_DIR / "target" / "release" / f"picking_current_best{suffix}"


def build_rust_solver() -> None:
    subprocess.run(["cargo", "build", "--release"], cwd=RUST_DIR, check=True)


def _float_note(notes: dict[str, Any], key: str) -> float:
    try:
        return float(notes.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _bool_note(notes: dict[str, Any], key: str) -> bool:
    return str(notes.get(key, "")).strip().lower() in {"1", "true", "yes", "y"}


def budget_label(budget: dict[str, Any], fallback_method: str) -> str:
    if budget["slug"] == "unlimited":
        return str(budget["label"])
    fallback_label = "visited-area" if fallback_method == "visited-area" else "GRASP"
    return str(budget["label"]).replace("GRASP", fallback_label)


def run_case(
    *,
    binary: Path,
    dataset: dict[str, Any],
    budget: dict[str, Any],
    cleanup_slug: str,
    cleanup_operator: str,
    strategy_slug: str,
    strategy_label: str,
    fallback_method: str,
    output_root: Path,
) -> dict[str, Any]:
    output_dir = output_root / dataset["slug"] / budget["slug"] / cleanup_slug / strategy_slug
    output_dir.mkdir(parents=True, exist_ok=True)
    pick_output = output_dir / "pick.csv"
    alt_output = output_dir / "alt.csv"
    summary_output = output_dir / "summary.json"
    log_output = output_dir / "run.log"

    command = [
        str(binary),
        "--orders",
        str(dataset["orders"]),
        "--stock",
        str(dataset["stock"]),
        "--time-limit",
        str(budget["time_limit"]),
        "--fallback-method",
        fallback_method,
        "--cleanup-operator",
        cleanup_operator,
        "--cleanup-strategy",
        strategy_slug,
        "--output",
        str(pick_output),
        "--alternative-locations-output",
        str(alt_output),
        "--summary-output",
        str(summary_output),
    ]
    if budget["slug"] == "unlimited":
        command.append("--no-fallback-on-time-limit")
    else:
        command.append("--fallback-on-time-limit")

    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
    log_output.write_text(
        "$ " + " ".join(command) + "\n\nSTDOUT:\n" + completed.stdout + "\nSTDERR:\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Rust solver failed for {dataset['slug']} / {budget['slug']} / {cleanup_slug} / {strategy_slug}. See {log_output}.")

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    notes = summary.get("notes", {})
    cleanup_time = _float_note(notes, "route_cleanup_time")
    row = {
        "dataset_slug": dataset["slug"],
        "dataset": dataset["label"],
        "orders": str(dataset["orders"]),
        "stock": str(dataset["stock"]),
        "budget_slug": budget["slug"],
        "budget": budget_label(budget, fallback_method),
        "time_limit": budget["time_limit"],
        "cleanup_slug": cleanup_slug,
        "cleanup": cleanup_operator,
        "strategy_slug": strategy_slug,
        "strategy": strategy_label,
        "fallback_method": str(notes.get("fallback_method", fallback_method)),
        "objective": float(summary["objective_value"]),
        "distance": float(summary["distance"]),
        "floors": int(summary["floors"]),
        "thms": int(summary["thms"]),
        "pick_rows": int(summary["pick_rows"]),
        "visited_nodes": int(summary["visited_nodes"]),
        "solve_time": float(summary["solve_time"]),
        "cleanup_time": cleanup_time,
        "construction_time": max(0.0, float(summary["solve_time"]) - cleanup_time),
        "timed_out": _bool_note(notes, "timed_out"),
        "fallback_used": _bool_note(notes, "fallback_used"),
        "remaining_units_before_fallback": int(str(notes.get("remaining_units_before_fallback", "0"))),
        "strict_steps": int(str(notes.get("strict_steps", "0"))),
        "strict_candidate_evals": int(str(notes.get("strict_candidate_evals", "0"))),
        "strict_position_evals": int(str(notes.get("strict_position_evals", "0"))),
        "fallback_steps": int(str(notes.get("fallback_steps", "0"))),
        "pick_output": str(pick_output),
        "alt_output": str(alt_output),
        "summary_output": str(summary_output),
        "log_output": str(log_output),
        "solver_summary": summary,
    }
    (output_dir / "benchmark_row.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def validate_pick_outputs(rows: list[dict[str, Any]]) -> None:
    demands_by_orders: dict[str, dict[int, int]] = {}
    for row in rows:
        orders = row["orders"]
        if orders not in demands_by_orders:
            demands_by_orders[orders] = load_demands(REPO_ROOT / orders)
        demands = demands_by_orders[orders]

        picked: dict[int, int] = defaultdict(int)
        with (REPO_ROOT / row["pick_output"]).open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for pick_row in reader:
                picked[int(pick_row["ARTICLE_CODE"])] += int(float(pick_row["AMOUNT"]))

        if any(picked.get(article, 0) != qty for article, qty in demands.items()):
            raise ValueError(f"Demand mismatch in {row['pick_output']}")
        if any(article not in demands for article in picked):
            raise ValueError(f"Unexpected picked article in {row['pick_output']}")


def write_report(rows: list[dict[str, Any]], report_path: Path) -> None:
    fallback_methods = sorted({str(row.get("fallback_method", "grasp")) for row in rows})
    fallback_label = ", ".join(fallback_methods) if fallback_methods else "grasp"
    lines = [
        "# Rust Current-Best Comprehensive Benchmark",
        "",
        "This report benchmarks the pure-Rust current-best solver across runtime budgets, cleanup operators, and first/best improvement strategies.",
        "",
        f"Pipeline: `one-location prep + pure-Rust seed route + ascending grouped strict insertion + open THM shortcut + {fallback_label} fallback + delta-cost cleanup`.",
        "",
        "Important difference vs Python: the Rust solver does not call the external LK package. Its seed route uses pure-Rust regret insertion plus 2-opt, so exact row-by-row routes may differ from Python.",
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
    parser = argparse.ArgumentParser(description="Benchmark the Rust current-best solver.")
    parser.add_argument("--output-dir", default="outputs/benchmark_outputs/rust_current_best_benchmark")
    parser.add_argument("--report", default="reports/benchmarks/RUST_CURRENT_BEST_BENCHMARK.md")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--only-dataset", action="append", default=[], help="Dataset slug(s), repeatable or comma-separated.")
    parser.add_argument("--only-budget", action="append", default=[], help="Budget slug(s), repeatable or comma-separated.")
    parser.add_argument("--only-cleanup", action="append", default=[], help="Cleanup slug(s), repeatable or comma-separated.")
    parser.add_argument("--only-strategy", action="append", default=[], help="Strategy slug(s), repeatable or comma-separated.")
    parser.add_argument("--fallback-method", choices=("grasp", "visited-area"), default="grasp")
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

    if not args.skip_build:
        build_rust_solver()
    binary = rust_binary_path()
    if not binary.exists():
        raise FileNotFoundError(f"Missing Rust binary: {binary}")

    output_root = REPO_ROOT / args.output_dir
    rows = []
    for dataset in DATASETS:
        if selected_datasets and dataset["slug"] not in selected_datasets:
            continue
        for budget in BUDGETS:
            if selected_budgets and budget["slug"] not in selected_budgets:
                continue
            for cleanup_slug, cleanup_operator in CLEANUPS:
                if selected_cleanups and cleanup_slug not in selected_cleanups:
                    continue
                for strategy_slug, strategy_label in STRATEGIES:
                    if selected_strategies and strategy_slug not in selected_strategies:
                        continue
                    print(
                        f"Running Rust {dataset['slug']} / {budget['slug']} / {cleanup_slug} / {strategy_slug} ...",
                        flush=True,
                    )
                    rows.append(
                        run_case(
                            binary=binary,
                            dataset=dataset,
                            budget=budget,
                            cleanup_slug=cleanup_slug,
                            cleanup_operator=cleanup_operator,
                            strategy_slug=strategy_slug,
                            strategy_label=strategy_label,
                            fallback_method=args.fallback_method,
                            output_root=output_root,
                        )
                    )

    validate_pick_outputs(rows)
    write_report(rows, REPO_ROOT / args.report)
    (output_root / "run_summary.json").write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps({"report": args.report, "rows": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

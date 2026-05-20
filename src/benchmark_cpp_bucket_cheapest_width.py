"""Benchmark bucket-cheapest C++ article selection across candidate-group widths."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CPP_DIR = REPO_ROOT / "cpp_solver"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "benchmark_outputs" / "cpp_bucket_cheapest_width_benchmark"
DEFAULT_REPORT = REPO_ROOT / "reports" / "benchmarks" / "CPP_BUCKET_CHEAPEST_WIDTH_BENCHMARK.md"


def cpp_binary_path() -> Path:
    suffix = ".exe" if sys.platform.startswith("win") else ""
    return CPP_DIR / "build" / f"picking_current_best_cpp{suffix}"


def build_cpp_solver(compiler: str) -> None:
    binary = cpp_binary_path()
    binary.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O3",
            "-Wall",
            "-Wextra",
            "-pedantic",
            "src/main.cpp",
            "-o",
            str(binary),
        ],
        cwd=CPP_DIR,
        check=True,
    )


def load_demands(path: Path) -> Counter[int]:
    demands: Counter[int] = Counter()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            demands[int(float(row["ARTICLE_CODE"]))] += int(float(row["AMOUNT"]))
    return demands


def stock_counts(path: Path) -> tuple[int, int]:
    rows = 0
    articles: set[int] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            value = row.get("ARTICLE_CODE", "")
            if value:
                articles.add(int(float(value)))
    return rows, len(articles)


def validate_pick(path: Path, demands: Counter[int]) -> None:
    picked: Counter[int] = Counter()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            picked[int(float(row["ARTICLE_CODE"]))] += int(float(row["AMOUNT"]))
    if picked != demands:
        mismatches = [
            (article, demands[article], picked[article])
            for article in sorted(set(demands) | set(picked))
            if demands[article] != picked[article]
        ]
        raise ValueError(f"Demand mismatch in {path}: {mismatches[:10]}")


def note_float(notes: dict[str, Any], key: str) -> float:
    try:
        return float(notes.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def note_int(notes: dict[str, Any], key: str) -> int:
    try:
        return int(float(notes.get(key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def bucket_label(width: int) -> str:
    if width == 0:
        return "all remaining"
    if width == 1:
        return "2, 3, 4, ..."
    return f"2-{width + 1}, {width + 2}-{2 * width + 1}, ..."


def run_width(
    *,
    binary: Path,
    width: int,
    orders: Path,
    stock: Path,
    output_dir: Path,
    time_limit: float,
    cleanup_operator: str,
    cleanup_strategy: str,
    cleanup_passes: int,
    fallback_method: str,
) -> dict[str, Any]:
    case_dir = output_dir / f"width_{width:02d}"
    case_dir.mkdir(parents=True, exist_ok=True)
    pick_output = case_dir / "pick.csv"
    alt_output = case_dir / "alt.csv"
    summary_output = case_dir / "summary.json"
    log_output = case_dir / "run.log"

    article_selection = "global-cheapest" if width == 0 else "bucket-cheapest"
    command = [
        str(binary),
        "--orders",
        str(orders),
        "--stock",
        str(stock),
        "--time-limit",
        str(time_limit),
        "--fallback-method",
        fallback_method,
        "--article-selection",
        article_selection,
        "--cleanup-operator",
        cleanup_operator,
        "--cleanup-strategy",
        cleanup_strategy,
        "--cleanup-passes",
        str(cleanup_passes),
        "--output",
        str(pick_output),
        "--alternative-locations-output",
        str(alt_output),
        "--summary-output",
        str(summary_output),
    ]
    if width > 0:
        command.extend(["--candidate-group-width", str(width)])

    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
    log_output.write_text(
        "$ " + " ".join(command) + "\n\nSTDOUT:\n" + completed.stdout + "\nSTDERR:\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"C++ solver failed for width={width}. See {log_output}.")

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    notes = summary.get("notes", {})
    cleanup_time = note_float(notes, "route_cleanup_time")
    row = {
        "width": width,
        "article_selection": str(notes.get("article_selection", article_selection)),
        "bucket_label": bucket_label(width),
        "objective": float(summary["objective_value"]),
        "distance": float(summary["distance"]),
        "floors": int(summary["floors"]),
        "thms": int(summary["thms"]),
        "pick_rows": int(summary["pick_rows"]),
        "visited_nodes": int(summary["visited_nodes"]),
        "solve_time": float(summary["solve_time"]),
        "construction_time": max(0.0, float(summary["solve_time"]) - cleanup_time),
        "cleanup_time": cleanup_time,
        "seed_route_time": note_float(notes, "seed_route_sec"),
        "selection_time": note_float(notes, "ascending_grouped_phase_sec"),
        "strict_steps": note_int(notes, "strict_steps"),
        "strict_candidate_evals": note_int(notes, "strict_candidate_evals"),
        "strict_position_evals": note_int(notes, "strict_position_evals"),
        "fallback_used": str(notes.get("fallback_used", "")).lower() == "true",
        "timed_out": str(notes.get("timed_out", "")).lower() == "true",
        "remaining_units_before_fallback": note_int(notes, "remaining_units_before_fallback"),
        "fallback_steps": note_int(notes, "fallback_steps"),
        "cleanup_passes_applied": note_int(notes, "cleanup_passes_applied"),
        "summary_output": str(summary_output),
        "pick_output": str(pick_output),
        "alt_output": str(alt_output),
        "log_output": str(log_output),
        "solver_summary": summary,
    }
    (case_dir / "benchmark_row.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def fmt_time(value: float) -> str:
    return f"{value:.2f}s" if value >= 10 else f"{value:.4f}s"


def write_report(
    *,
    rows: list[dict[str, Any]],
    report_path: Path,
    output_dir: Path,
    orders: Path,
    stock: Path,
    demand_articles: int,
    total_demand: int,
    stock_rows: int,
    stock_articles: int,
    time_limit: float,
    cleanup_operator: str,
    cleanup_strategy: str,
    cleanup_passes: int,
) -> None:
    rows = sorted(rows, key=lambda row: row["width"])
    best = min(rows, key=lambda row: row["objective"])
    fastest = min(rows, key=lambda row: row["solve_time"])
    width_two = next((row for row in rows if row["width"] == 2), None)

    lines = [
        "# C++ Bucket-Cheapest Width Benchmark",
        "",
        "This report benchmarks the bucket-cheapest article selection mode on the full dataset.",
        "",
        "Pipeline: `one-location prep + LKH-3 seed route + bucket/global strict cheapest insertion + GRASP fallback if capped + delta-cost cleanup`.",
        "",
        "Common objective: `distance + 15 * opened THMs + 30 * active floors`.",
        "",
        "## Setup",
        "",
        f"- Orders: `{orders}`",
        f"- Stock: `{stock}`",
        f"- Demand articles: `{demand_articles}`",
        f"- Total demand amount: `{total_demand}`",
        f"- Stock rows / stock articles: `{stock_rows}` / `{stock_articles}`",
        f"- Runtime cap: `{time_limit:.0f}s` with GRASP fallback enabled",
        f"- Seed route: `LKH-3 explicit full-matrix depot cycle`",
        f"- Cleanup: `{cleanup_operator}` / `{cleanup_strategy}` / `{cleanup_passes}` passes",
        "",
        "Width `0` is the all-remaining global-cheapest baseline. Widths `1-5` use bucket-cheapest, where buckets are processed in candidate-count order and the cheapest strict insertion is selected within the active bucket.",
        "",
        "## Results",
        "",
        "| Width | Mode | Candidate buckets | Objective | Delta vs best | Distance | THMs | Pick rows | Visited nodes | Cap hit? | Fallback units | Strict steps | Strict evals | Position evals | Cleanup passes | Selection time | Cleanup time | Total time |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["width"]),
                    f"`{row['article_selection']}`",
                    f"`{row['bucket_label']}`",
                    fmt(row["objective"]),
                    fmt(row["objective"] - best["objective"]),
                    fmt(row["distance"]),
                    str(row["thms"]),
                    str(row["pick_rows"]),
                    str(row["visited_nodes"]),
                    "Yes" if row["timed_out"] else "No",
                    str(row["remaining_units_before_fallback"]),
                    str(row["strict_steps"]),
                    str(row["strict_candidate_evals"]),
                    str(row["strict_position_evals"]),
                    str(row["cleanup_passes_applied"]),
                    fmt_time(row["selection_time"]),
                    fmt_time(row["cleanup_time"]),
                    fmt_time(row["solve_time"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Takeaways",
            "",
            f"- Best objective: width `{best['width']}` with `{best['objective']:.2f}`.",
            f"- Fastest run: width `{fastest['width']}` in `{fastest['solve_time']:.2f}s`.",
            "- Width `0` and any capped rows include GRASP fallback, so they are not pure strict-cheapest completions.",
        ]
    )
    if width_two:
        lines.append(
            f"- Width `2` completed without fallback in `{width_two['solve_time']:.2f}s` and is the current strongest bucket-cheapest candidate in this sweep."
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- Run outputs: `{output_dir.relative_to(REPO_ROOT)}`",
            f"- Summary JSON: `{(output_dir / 'run_summary.json').relative_to(REPO_ROOT)}`",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark bucket-cheapest widths for the C++ solver.")
    parser.add_argument("--orders", default="data/full/PickOrder.csv")
    parser.add_argument("--stock", default="data/full/StockData.csv")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)))
    parser.add_argument("--report", default=str(DEFAULT_REPORT.relative_to(REPO_ROOT)))
    parser.add_argument("--compiler", default="c++")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--min-width", type=int, default=0)
    parser.add_argument("--max-width", type=int, default=5)
    parser.add_argument("--time-limit", type=float, default=120.0)
    parser.add_argument("--cleanup-operator", default="2-opt")
    parser.add_argument("--cleanup-strategy", default="best")
    parser.add_argument("--cleanup-passes", type=int, default=3)
    parser.add_argument("--fallback-method", default="grasp")
    args = parser.parse_args()

    orders = Path(args.orders)
    stock = Path(args.stock)
    output_dir = Path(args.output_dir)
    report_path = Path(args.report)
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    if not report_path.is_absolute():
        report_path = REPO_ROOT / report_path

    if not args.skip_build:
        build_cpp_solver(args.compiler)
    binary = cpp_binary_path()
    if not binary.exists():
        raise FileNotFoundError(binary)

    demands = load_demands(REPO_ROOT / orders)
    stock_rows, stock_articles = stock_counts(REPO_ROOT / stock)
    rows: list[dict[str, Any]] = []
    for width in range(args.min_width, args.max_width + 1):
        print(f"Running width={width}...")
        row = run_width(
            binary=binary,
            width=width,
            orders=orders,
            stock=stock,
            output_dir=output_dir,
            time_limit=args.time_limit,
            cleanup_operator=args.cleanup_operator,
            cleanup_strategy=args.cleanup_strategy,
            cleanup_passes=args.cleanup_passes,
            fallback_method=args.fallback_method,
        )
        validate_pick(REPO_ROOT / row["pick_output"], demands)
        rows.append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    run_summary = {
        "orders": str(orders),
        "stock": str(stock),
        "widths": list(range(args.min_width, args.max_width + 1)),
        "time_limit": args.time_limit,
        "cleanup_operator": args.cleanup_operator,
        "cleanup_strategy": args.cleanup_strategy,
        "cleanup_passes": args.cleanup_passes,
        "fallback_method": args.fallback_method,
        "rows": rows,
    }
    (output_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    write_report(
        rows=rows,
        report_path=report_path,
        output_dir=output_dir,
        orders=orders,
        stock=stock,
        demand_articles=len(demands),
        total_demand=sum(demands.values()),
        stock_rows=stock_rows,
        stock_articles=stock_articles,
        time_limit=args.time_limit,
        cleanup_operator=args.cleanup_operator,
        cleanup_strategy=args.cleanup_strategy,
        cleanup_passes=args.cleanup_passes,
    )
    print(f"Report written to {report_path}")
    print(f"Run summary written to {output_dir / 'run_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

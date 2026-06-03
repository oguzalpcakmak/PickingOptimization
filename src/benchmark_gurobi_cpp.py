#!/usr/bin/env python3
"""Run reproducible corrected-Gurobi vs C++ heuristic benchmark profiles."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FLOORS = ("MZN1", "MZN2", "MZN3")
WEIGHTS = {"distance": 1.0, "thm": 15.0, "floor": 30.0}


@dataclass(frozen=True)
class BenchmarkProfile:
    title: str
    articles: tuple[int, ...]
    output_dir: Path
    report: Path


BENCHMARK_PROFILES = {
    "10item": BenchmarkProfile(
        title="10-Item Benchmark",
        articles=(567, 577, 606, 609, 699, 788, 791, 866, 977, 993),
        output_dir=REPO_ROOT / "outputs/benchmark_outputs/gurobi_cpp_10item",
        report=REPO_ROOT / "reports/benchmarks/GUROBI_CPP_10_ITEM_BENCHMARK.md",
    ),
    "25item3floor": BenchmarkProfile(
        title="25-Item / 3-Floor Benchmark",
        articles=(
            567,
            577,
            606,
            609,
            699,
            788,
            791,
            866,
            977,
            993,
            997,
            999,
            1019,
            1020,
            1030,
            1051,
            1055,
            1061,
            1066,
            1068,
            1087,
            1088,
            1093,
            1118,
            1122,
        ),
        output_dir=REPO_ROOT / "outputs/benchmark_outputs/gurobi_cpp_25item3floor",
        report=REPO_ROOT / "reports/benchmarks/GUROBI_CPP_25_ITEM_3_FLOOR_BENCHMARK.md",
    ),
}


def parse_args(default_profile: str = "10item") -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=sorted(BENCHMARK_PROFILES),
        default=default_profile,
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=120.0,
        help="Solver time limit in seconds. Use 0 for unlimited.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
    )
    parser.add_argument("--skip-cpp-build", action="store_true")
    return parser.parse_args()


def with_gurobi_pythonpath() -> dict[str, str]:
    env = dict(os.environ)
    if importlib.util.find_spec("gurobipy") is not None:
        return env

    site_packages = sorted((REPO_ROOT / ".venv/lib").glob("python*/site-packages"))
    if site_packages:
        existing = env.get("PYTHONPATH", "")
        entries = [str(site_packages[-1])]
        if existing:
            entries.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def run_command(
    command: list[str],
    log_path: Path,
    *,
    env: dict[str, str] | None = None,
) -> float:
    started_at = time.perf_counter()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        return_code = process.wait()
    runtime = time.perf_counter() - started_at
    if return_code != 0:
        raise RuntimeError(
            f"Command failed with exit code {return_code}: {' '.join(command)}. "
            f"See {log_path}."
        )
    return runtime


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def demand_totals(path: Path, selected_articles: Iterable[int]) -> dict[int, int]:
    selected = set(selected_articles)
    totals: dict[int, int] = defaultdict(int)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            article = int(float(row["ARTICLE_CODE"]))
            if article in selected:
                totals[article] += int(float(row["AMOUNT"]))
    return dict(sorted(totals.items()))


def picked_totals(path: Path) -> dict[int, int]:
    totals: dict[int, int] = defaultdict(int)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            article = int(float(row["ARTICLE_CODE"]))
            totals[article] += int(float(row["AMOUNT"]))
    return dict(sorted(totals.items()))


def validate_pick_totals(
    expected: dict[int, int],
    actual_path: Path,
    solver_name: str,
) -> None:
    actual = picked_totals(actual_path)
    if actual != expected:
        raise RuntimeError(
            f"{solver_name} pick totals do not match the selected demand. "
            f"Expected {expected}, got {actual}."
        )


def validate_objective(summary: dict[str, Any], solver_name: str) -> None:
    expected = (
        WEIGHTS["distance"] * float(summary["distance"])
        + WEIGHTS["thm"] * int(summary["thms"])
        + WEIGHTS["floor"] * int(summary["floors"])
    )
    if not math.isclose(expected, float(summary["objective_value"]), abs_tol=1e-4):
        raise RuntimeError(
            f"{solver_name} objective mismatch: expected {expected}, "
            f"got {summary['objective_value']}."
        )


def format_float(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def relative_repo_path(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def write_report(
    report_path: Path,
    run_summary_path: Path,
    run_summary: dict[str, Any],
) -> None:
    gurobi = run_summary["gurobi"]
    cpp = run_summary["cpp"]
    delta = run_summary["delta_vs_gurobi"]
    gap = gurobi.get("mip_gap")
    gap_text = "n/a" if gap is None else f"{100.0 * float(gap):.4f}%"
    time_limit_text = (
        "unlimited"
        if run_summary["time_limit_seconds"] <= 0
        else f'{run_summary["time_limit_seconds"]:.0f}s time limit'
    )
    title = run_summary.get("title", f"{len(run_summary['articles'])}-Item Benchmark")
    baseline_name = "Gurobi optimum" if gurobi["is_optimal"] else "Gurobi incumbent"
    if gurobi["is_optimal"]:
        interpretation = (
            "- Gurobi proved optimality, so the C++ delta is an exact optimality gap "
            "for this benchmark."
        )
    else:
        cpp_gap_vs_bound = (
            100.0
            * (float(cpp["objective_value"]) - float(gurobi["best_bound"]))
            / float(gurobi["best_bound"])
        )
        interpretation = (
            f"- Gurobi reached the time limit without proving optimality. The C++ result "
            f"is `{format_float(delta['percent'])}%` above the Gurobi incumbent. Given "
            f"the `{format_float(gurobi['best_bound'])}` lower bound, the C++ solution's "
            f"true optimality gap is between `{format_float(delta['percent'])}%` and "
            f"`{format_float(cpp_gap_vs_bound)}%` under this model."
        )

    report = f"""# Gurobi vs C++ Heuristic: {title}

Generated: `{run_summary["generated_at"]}`

## Setup

- Source orders: `{run_summary["orders"]}`
- Source stock: `{run_summary["stock"]}`
- Articles: `{", ".join(str(article) for article in run_summary["articles"])}`
- Total pick amount: `{run_summary["total_pick_amount"]}`
- Floors: `{", ".join(run_summary["floors"])}`
- Objective: `distance + 15 * THMs + 30 * active floors`
- C++ mode: `bucket-cheapest`, width `2`, LKH seed route, `2-opt best`, `3` cleanup passes
- Gurobi mode: MIP model with `--mip-gap 0` and `{time_limit_text}`

## Results

| Solver | Status | Objective | Delta vs {baseline_name} | Distance | Floors | THMs | Pick rows | Visited nodes | Runtime |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Corrected Gurobi MIP model | `{gurobi["status"]}` | {format_float(gurobi["objective_value"])} | 0.00 | {format_float(gurobi["distance"])} | {gurobi["floors"]} | {gurobi["thms"]} | {gurobi["pick_rows"]} | {gurobi["visited_nodes"]} | {format_float(gurobi["runtime"], 4)}s |
| C++ current heuristic | `COMPLETED` | {format_float(cpp["objective_value"])} | {format_float(delta["absolute"])} ({format_float(delta["percent"])}%) | {format_float(cpp["distance"])} | {cpp["floors"]} | {cpp["thms"]} | {cpp["pick_rows"]} | {cpp["visited_nodes"]} | {format_float(cpp["solve_time"], 4)}s |

## Gurobi Solve

- Best bound: `{format_float(gurobi["best_bound"])}`
- MIP gap: `{gap_text}`
- Proven optimal: `{"yes" if gurobi["is_optimal"] else "no"}`
- Variables: `{gurobi["variables"]}`
- Constraints: `{gurobi["constraints"]}`
- Routing arcs: `{gurobi["routing_arcs"]}`

## Interpretation

{interpretation}

## Validation

- Both solver outputs reproduce the selected demand totals exactly.
- Both reported objective values were recomputed from distance, THM count, and active-floor count.
- The comparison uses the same CSV sources, article filter, floor filter, and weights.
- This run uses the current `1 / 15 / 30` project weights. Legacy `1 / 1 / 1` benchmark objectives are not directly comparable.

## Artifacts

- Run summary: `{relative_repo_path(run_summary_path)}`
- Gurobi summary: `{run_summary["artifacts"]["gurobi_summary"]}`
- Gurobi pick output: `{run_summary["artifacts"]["gurobi_pick"]}`
- C++ summary: `{run_summary["artifacts"]["cpp_summary"]}`
- C++ pick output: `{run_summary["artifacts"]["cpp_pick"]}`
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def main(default_profile: str = "10item") -> int:
    args = parse_args(default_profile)
    profile = BENCHMARK_PROFILES[args.profile]
    output_dir = (args.output_dir or profile.output_dir).resolve()
    report_path = (args.report or profile.report).resolve()
    orders = Path("data/25item3floor/PickOrder.csv")
    stock = Path("data/25item3floor/StockData.csv")
    article_filter = ",".join(str(article) for article in profile.articles)
    floor_filter = ",".join(DEFAULT_FLOORS)

    gurobi_dir = output_dir / "gurobi"
    cpp_dir = output_dir / "cpp_bucket_cheapest_width_2"
    gurobi_summary_path = gurobi_dir / "summary.json"
    gurobi_pick_path = gurobi_dir / "pick.csv"
    gurobi_alt_path = gurobi_dir / "alt.csv"
    cpp_summary_path = cpp_dir / "summary.json"
    cpp_pick_path = cpp_dir / "pick.csv"
    cpp_alt_path = cpp_dir / "alt.csv"
    run_summary_path = output_dir / "run_summary.json"

    if not args.skip_cpp_build:
        run_command(
            ["cmake", "--build", "cpp_solver/build", "--target", "picking_current_best_cpp", "-j"],
            output_dir / "cpp_build.log",
        )

    gurobi_env = with_gurobi_pythonpath()
    gurobi_env["GRB_LICENSE_FILE"] = str(REPO_ROOT / "gurobi.lic")
    gurobi_env["PYTHONUNBUFFERED"] = "1"
    gurobi_command = [
            sys.executable,
            "-u",
            "src/gurobi_pick_model.py",
            "--orders",
            str(orders),
            "--stock",
            str(stock),
            "--floors",
            floor_filter,
            "--articles",
            article_filter,
            "--distance-weight",
            str(WEIGHTS["distance"]),
            "--thm-weight",
            str(WEIGHTS["thm"]),
            "--floor-weight",
            str(WEIGHTS["floor"]),
            "--mip-gap",
            "0",
            "--optimize",
            "--pick-data-output",
            str(gurobi_pick_path),
            "--alternative-locations-output",
            str(gurobi_alt_path),
            "--summary-output",
            str(gurobi_summary_path),
        ]
    if args.time_limit > 0:
        gurobi_command[17:17] = ["--time-limit", str(args.time_limit)]

    gurobi_wall_time = run_command(
        gurobi_command,
        gurobi_dir / "run.log",
        env=gurobi_env,
    )

    cpp_wall_time = run_command(
        [
            "cpp_solver/build/picking_current_best_cpp",
            "--orders",
            str(orders),
            "--stock",
            str(stock),
            "--floors",
            floor_filter,
            "--articles",
            article_filter,
            "--distance-weight",
            str(WEIGHTS["distance"]),
            "--thm-weight",
            str(WEIGHTS["thm"]),
            "--floor-weight",
            str(WEIGHTS["floor"]),
            "--time-limit",
            str(args.time_limit),
            "--seed-route-optimizer",
            "lkh",
            "--lkh-path",
            "external/LKH-3.0.14/LKH",
            "--article-selection",
            "bucket-cheapest",
            "--candidate-group-width",
            "2",
            "--fallback-method",
            "grasp",
            "--cleanup-operator",
            "2-opt",
            "--cleanup-strategy",
            "best",
            "--cleanup-passes",
            "3",
            "--output",
            str(cpp_pick_path),
            "--alternative-locations-output",
            str(cpp_alt_path),
            "--summary-output",
            str(cpp_summary_path),
        ],
        cpp_dir / "run.log",
    )

    gurobi = read_json(gurobi_summary_path)
    cpp = read_json(cpp_summary_path)
    expected_demands = demand_totals(REPO_ROOT / orders, profile.articles)
    validate_pick_totals(expected_demands, gurobi_pick_path, "Gurobi")
    validate_pick_totals(expected_demands, cpp_pick_path, "C++")
    validate_objective(gurobi, "Gurobi")
    validate_objective(cpp, "C++")

    gurobi_objective = float(gurobi["objective_value"])
    cpp_objective = float(cpp["objective_value"])
    delta = cpp_objective - gurobi_objective
    run_summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "profile": args.profile,
        "title": profile.title,
        "orders": str(orders),
        "stock": str(stock),
        "articles": list(profile.articles),
        "total_pick_amount": sum(expected_demands.values()),
        "floors": list(DEFAULT_FLOORS),
        "weights": WEIGHTS,
        "time_limit_seconds": args.time_limit,
        "gurobi": {**gurobi, "wall_time": gurobi_wall_time},
        "cpp": {**cpp, "wall_time": cpp_wall_time},
        "delta_vs_gurobi": {
            "absolute": delta,
            "percent": 100.0 * delta / gurobi_objective,
        },
        "validation": {
            "demand_totals_match": True,
            "objective_recomputation_match": True,
        },
        "artifacts": {
            "gurobi_summary": relative_repo_path(gurobi_summary_path),
            "gurobi_pick": relative_repo_path(gurobi_pick_path),
            "gurobi_alternatives": relative_repo_path(gurobi_alt_path),
            "cpp_summary": relative_repo_path(cpp_summary_path),
            "cpp_pick": relative_repo_path(cpp_pick_path),
            "cpp_alternatives": relative_repo_path(cpp_alt_path),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    run_summary_path.write_text(
        json.dumps(run_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(report_path, run_summary_path, run_summary)

    print(f"Benchmark summary written to {run_summary_path}")
    print(f"Benchmark report written to {report_path}")
    print(f"Gurobi objective: {gurobi_objective:.2f}")
    print(f"C++ objective: {cpp_objective:.2f}")
    print(f"C++ delta vs Gurobi: {delta:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

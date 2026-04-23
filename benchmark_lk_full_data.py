from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from heuristic_common import print_report, write_alternative_locations_csv, write_pick_csv
from lk_warehouse_heuristic import solve


REPO_ROOT = Path(__file__).resolve().parent


@dataclass
class BenchmarkRow:
    solver: str
    comparable_objective: float
    native_objective: float
    distance: float
    floors: int
    thms: int
    pick_rows: int
    visited_nodes: int
    solve_time: float
    status: str
    route_optimizer: str
    lk_backtracking: str
    lk_reduction_level: int
    lk_reduction_cycle: int
    pick_output: str
    alt_output: str


def _visited_nodes(solution) -> int:
    return sum(floor_result.visited_nodes for floor_result in solution.floor_results)


def run_benchmark(
    *,
    orders: str,
    stock: str,
    output_dir: Path,
) -> BenchmarkRow:
    output_dir.mkdir(parents=True, exist_ok=True)

    solution = solve(
        orders,
        stock,
        distance_weight=1.0,
        thm_weight=15.0,
        floor_weight=30.0,
        construction_route_estimator="insertion",
        route_optimizer="lk2_improve",
        lk_backtracking=(5, 5),
        lk_reduction_level=4,
        lk_reduction_cycle=4,
        route_rebuild_threshold=60,
    )

    pick_output = output_dir / "lk_regret_full_pick.csv"
    alt_output = output_dir / "lk_regret_full_alt.csv"
    write_pick_csv(solution, pick_output)
    write_alternative_locations_csv(solution, alt_output)
    print_report(solution)
    print(f"Pick CSV written to {pick_output}")
    print(f"Alternative CSV written to {alt_output}")

    return BenchmarkRow(
        solver="Route-aware regret + LK2 routing",
        comparable_objective=round(solution.objective_value, 2),
        native_objective=round(solution.objective_value, 2),
        distance=round(solution.total_distance, 2),
        floors=solution.total_floors,
        thms=solution.total_thms,
        pick_rows=solution.total_picks,
        visited_nodes=_visited_nodes(solution),
        solve_time=round(solution.solve_time, 2),
        status="Completed",
        route_optimizer="lk2_improve",
        lk_backtracking="5,5",
        lk_reduction_level=4,
        lk_reduction_cycle=4,
        pick_output=str(pick_output.relative_to(REPO_ROOT)).replace("\\", "/"),
        alt_output=str(alt_output.relative_to(REPO_ROOT)).replace("\\", "/"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the full-data LK warehouse benchmark.")
    parser.add_argument("--orders", default="PickOrder.csv")
    parser.add_argument("--stock", default="StockData.csv")
    parser.add_argument("--output-dir", default="benchmark_outputs/full_data_lk")
    parser.add_argument("--summary-output", default="benchmark_outputs/full_data_lk/run_summary.json")
    args = parser.parse_args(argv)

    row = run_benchmark(
        orders=args.orders,
        stock=args.stock,
        output_dir=REPO_ROOT / args.output_dir,
    )

    summary_path = REPO_ROOT / args.summary_output
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "orders": args.orders,
        "stock": args.stock,
        "weights": {"distance": 1, "thm": 15, "floor": 30},
        "row": asdict(row),
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    print(f"Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

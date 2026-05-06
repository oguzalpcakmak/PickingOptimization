from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from heuristic_common import print_report, write_alternative_locations_csv, write_pick_csv
from imported_tsp_warehouse_heuristic import ROUTE_OPTIMIZER_LABELS, solve


REPO_ROOT = Path(__file__).resolve().parents[1]


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
    pick_output: str
    alt_output: str


BENCHMARK_CONFIG = {
    "imported_city_swap": {
        "solver_label": "Route-aware regret + imported city swap routing",
        "pick_name": "imported_city_swap_full_pick.csv",
        "alt_name": "imported_city_swap_full_alt.csv",
    },
    "imported_simulated_annealing": {
        "solver_label": "Route-aware regret + imported simulated annealing routing",
        "pick_name": "imported_sa_full_pick.csv",
        "alt_name": "imported_sa_full_alt.csv",
    },
    "imported_genetic": {
        "solver_label": "Route-aware regret + imported genetic routing",
        "pick_name": "imported_genetic_full_pick.csv",
        "alt_name": "imported_genetic_full_alt.csv",
    },
}


def _visited_nodes(solution) -> int:
    return sum(floor_result.visited_nodes for floor_result in solution.floor_results)


def run_benchmark(
    *,
    orders: str,
    stock: str,
    output_dir: Path,
) -> list[BenchmarkRow]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[BenchmarkRow] = []

    for route_optimizer, config in BENCHMARK_CONFIG.items():
        solution = solve(
            orders,
            stock,
            distance_weight=1.0,
            thm_weight=15.0,
            floor_weight=30.0,
            construction_route_estimator="insertion",
            route_optimizer=route_optimizer,
            route_rebuild_threshold=60,
        )

        pick_output = output_dir / config["pick_name"]
        alt_output = output_dir / config["alt_name"]
        write_pick_csv(solution, pick_output)
        write_alternative_locations_csv(solution, alt_output)
        print_report(solution)
        print(f"Pick CSV written to {pick_output}")
        print(f"Alternative CSV written to {alt_output}")
        print()

        rows.append(
            BenchmarkRow(
                solver=config["solver_label"],
                comparable_objective=round(solution.objective_value, 2),
                native_objective=round(solution.objective_value, 2),
                distance=round(solution.total_distance, 2),
                floors=solution.total_floors,
                thms=solution.total_thms,
                pick_rows=solution.total_picks,
                visited_nodes=_visited_nodes(solution),
                solve_time=round(solution.solve_time, 2),
                status="Completed",
                route_optimizer=route_optimizer,
                pick_output=str(pick_output.relative_to(REPO_ROOT)).replace("\\", "/"),
                alt_output=str(alt_output.relative_to(REPO_ROOT)).replace("\\", "/"),
            )
        )

    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the imported TSP full-data benchmark suite.")
    parser.add_argument("--orders", default="data/full/PickOrder.csv")
    parser.add_argument("--stock", default="data/full/StockData.csv")
    parser.add_argument("--output-dir", default="outputs/benchmark_outputs/full_data_imported_tsp")
    parser.add_argument("--summary-output", default="outputs/benchmark_outputs/full_data_imported_tsp/run_summary.json")
    args = parser.parse_args(argv)

    rows = run_benchmark(
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
        "route_optimizers": {key: ROUTE_OPTIMIZER_LABELS[key] for key in BENCHMARK_CONFIG},
        "rows": [asdict(row) for row in rows],
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    print(f"Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

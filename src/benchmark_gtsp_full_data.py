from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from timeit import default_timer as timer


REPO_ROOT = Path(__file__).resolve().parents[1]
GTSP_ROOT = REPO_ROOT / "external" / "GTSP-master"
if str(GTSP_ROOT) not in sys.path:
    sys.path.insert(0, str(GTSP_ROOT))

from Algorithms import Annealing, Antcolony, Genetic, Tabu
from heuristic_common import ObjectiveWeights, print_report, write_alternative_locations_csv, write_pick_csv
from warehouse_problem import WarehouseGTSPAdapter


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
    candidate_cap: int
    iterations: int
    extra: dict[str, float | int | str]
    pick_output: str
    alt_output: str


BENCHMARK_CONFIG = {
    "gtsp_annealing": {
        "solver_label": "GTSP Simulated Annealing (cap 4)",
        "algorithm_cls": Annealing,
        "candidate_cap": 4,
        "iterations": 3,
        "params": {
            "initial_temperature": 10.0,
            "end_temperature": 0.1,
            "cooling_rate": 0.99,
            "inner_loops": 8,
        },
    },
    "gtsp_tabu": {
        "solver_label": "GTSP Tabu Search (cap 4)",
        "algorithm_cls": Tabu,
        "candidate_cap": 4,
        "iterations": 3,
        "params": {
            "tabu_length": None,
            "neighborhood_size": 8,
        },
    },
    "gtsp_genetic": {
        "solver_label": "GTSP Genetic Algorithm (cap 4)",
        "algorithm_cls": Genetic,
        "candidate_cap": 4,
        "iterations": 3,
        "params": {
            "population": 8,
            "crossRate": 0.8,
            "varyRate": 0.2,
            "eliteFraction": 0.1,
        },
    },
    "gtsp_antcolony": {
        "solver_label": "GTSP Ant Colony (cap 4)",
        "algorithm_cls": Antcolony,
        "candidate_cap": 4,
        "iterations": 1,
        "params": {
            "colony_size": 1,
            "alpha": 1.0,
            "beta": 2.0,
            "evaporation": 0.35,
            "q": 100.0,
        },
    },
}


def _visited_nodes(solution) -> int:
    return sum(floor_result.visited_nodes for floor_result in solution.floor_results)


def run_benchmark(
    *,
    orders: str,
    stock: str,
    output_dir: Path,
    seed: int,
) -> list[BenchmarkRow]:
    output_dir.mkdir(parents=True, exist_ok=True)
    weights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0)
    rows: list[BenchmarkRow] = []

    for offset, (run_name, config) in enumerate(BENCHMARK_CONFIG.items()):
        adapter = WarehouseGTSPAdapter(
            orders,
            stock,
            weights=weights,
            max_candidates_per_article=int(config["candidate_cap"]),
        )

        algorithm = config["algorithm_cls"](problem=adapter.problem, seed=seed + offset)
        algorithm.set_seed_paths(adapter.build_seed_paths())
        algorithm.set(**config["params"])

        started = timer()
        best_path, _ = algorithm.fit(int(config["iterations"]))
        elapsed = timer() - started

        solution = adapter.build_solution_from_path(
            best_path,
            algorithm=run_name,
            solve_time=elapsed,
            phase_times={"search": elapsed},
            route_estimator="insertion",
            route_rebuild_threshold=60,
            notes={
                "Benchmark run": config["solver_label"],
                "Candidate cap": int(config["candidate_cap"]),
                "Iterations": int(config["iterations"]),
            },
        )

        pick_output = output_dir / f"{run_name}_pick.csv"
        alt_output = output_dir / f"{run_name}_alt.csv"
        write_pick_csv(solution, pick_output)
        write_alternative_locations_csv(solution, alt_output)
        print_report(solution)
        print(f"Pick CSV written to {pick_output}")
        print(f"Alternative CSV written to {alt_output}")
        print()

        rows.append(
            BenchmarkRow(
                solver=str(config["solver_label"]),
                comparable_objective=round(solution.objective_value, 2),
                native_objective=round(solution.objective_value, 2),
                distance=round(solution.total_distance, 2),
                floors=solution.total_floors,
                thms=solution.total_thms,
                pick_rows=solution.total_picks,
                visited_nodes=_visited_nodes(solution),
                solve_time=round(solution.solve_time, 2),
                status="Completed",
                candidate_cap=int(config["candidate_cap"]),
                iterations=int(config["iterations"]),
                extra=dict(config["params"]),
                pick_output=str(pick_output.relative_to(REPO_ROOT)).replace("\\", "/"),
                alt_output=str(alt_output.relative_to(REPO_ROOT)).replace("\\", "/"),
            )
        )

    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the GTSP full-data benchmark suite.")
    parser.add_argument("--orders", default="data/full/PickOrder.csv")
    parser.add_argument("--stock", default="data/full/StockData.csv")
    parser.add_argument("--output-dir", default="outputs/benchmark_outputs/full_data_gtsp")
    parser.add_argument("--summary-output", default="outputs/benchmark_outputs/full_data_gtsp/run_summary.json")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    rows = run_benchmark(
        orders=args.orders,
        stock=args.stock,
        output_dir=REPO_ROOT / args.output_dir,
        seed=args.seed,
    )

    summary_path = REPO_ROOT / args.summary_output
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "orders": args.orders,
        "stock": args.stock,
        "weights": {"distance": 1, "thm": 15, "floor": 30},
        "rows": [asdict(row) for row in rows],
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    print(f"Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

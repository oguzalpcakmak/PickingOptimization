from __future__ import annotations

import argparse
from pathlib import Path
import sys
from timeit import default_timer as timer


REPO_ROOT = Path(__file__).resolve().parent
GTSP_ROOT = REPO_ROOT / "GTSP-master"
if str(GTSP_ROOT) not in sys.path:
    sys.path.insert(0, str(GTSP_ROOT))

from Algorithms import Annealing, Antcolony, Genetic, Tabu
from heuristic_common import (
    DataError,
    ObjectiveWeights,
    parse_article_list,
    parse_floor_list,
    print_report,
    write_alternative_locations_csv,
    write_pick_csv,
)
from warehouse_problem import WarehouseGTSPAdapter


ALGORITHMS = {
    "annealing": Annealing,
    "antcolony": Antcolony,
    "genetic": Genetic,
    "tabu": Tabu,
}


def _default_output_dir() -> Path:
    return REPO_ROOT / "benchmark_outputs" / "gtsp"


def _resolve_output_paths(
    algorithm: str,
    *,
    pick_data_output: str | None,
    alternative_locations_output: str | None,
    output_dir: str | None,
) -> tuple[Path, Path]:
    if pick_data_output and alternative_locations_output:
        return Path(pick_data_output), Path(alternative_locations_output)

    base_dir = Path(output_dir) if output_dir else _default_output_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    return (
        base_dir / f"{algorithm}_pick.csv",
        base_dir / f"{algorithm}_alt.csv",
    )


def _build_algorithm(name: str, adapter: WarehouseGTSPAdapter, args: argparse.Namespace, *, seed_offset: int = 0):
    algorithm_cls = ALGORITHMS[name]
    seed = None if args.seed is None else int(args.seed) + seed_offset
    algorithm = algorithm_cls(problem=adapter.problem, seed=seed)
    seed_paths = adapter.build_seed_paths()
    algorithm.set_seed_paths(seed_paths)

    if name == "genetic":
        algorithm.set(
            population=args.population,
            crossRate=args.cross_rate,
            varyRate=args.vary_rate,
            eliteFraction=args.elite_fraction,
        )
    elif name == "antcolony":
        algorithm.set(
            colony_size=args.colony_size,
            alpha=args.alpha,
            beta=args.beta,
            evaporation=args.evaporation,
            q=args.pheromone_q,
        )
    elif name == "annealing":
        algorithm.set(
            initial_temperature=args.initial_temperature,
            end_temperature=args.end_temperature,
            cooling_rate=args.cooling_rate,
            inner_loops=args.inner_loops,
        )
    elif name == "tabu":
        algorithm.set(
            tabu_length=args.tabu_length,
            neighborhood_size=args.neighborhood_size,
        )

    return algorithm


def run_single_algorithm(
    name: str,
    adapter: WarehouseGTSPAdapter,
    args: argparse.Namespace,
    *,
    seed_offset: int = 0,
) -> None:
    algorithm = _build_algorithm(name, adapter, args, seed_offset=seed_offset)

    search_start = timer()
    best_path, best_primary_cost = algorithm.fit(args.iterations)
    search_elapsed = timer() - search_start

    solution = adapter.build_solution_from_path(
        best_path,
        algorithm=f"gtsp_{name}",
        solve_time=search_elapsed,
        phase_times={"search": search_elapsed},
        route_estimator=args.route_estimator,
        route_rebuild_threshold=args.route_rebuild_threshold,
        notes={
            "Primary search best": f"{best_primary_cost:.2f}",
            "Iterations": args.iterations,
        },
    )

    pick_path, alt_path = _resolve_output_paths(
        name,
        pick_data_output=args.pick_data_output if args.algorithm != "all" else None,
        alternative_locations_output=args.alternative_locations_output if args.algorithm != "all" else None,
        output_dir=args.output_dir,
    )

    write_pick_csv(solution, pick_path)
    write_alternative_locations_csv(solution, alt_path)

    print_report(solution)
    print(f"Pick CSV written to {pick_path}")
    print(f"Alternative CSV written to {alt_path}")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GTSP-master heuristics on warehouse picking data.")
    parser.add_argument(
        "--algorithm",
        choices=[*ALGORITHMS.keys(), "all"],
        default="annealing",
        help="Which GTSP-master heuristic to run.",
    )
    parser.add_argument("--orders", required=True, help="Path to PickOrder.csv")
    parser.add_argument("--stock", required=True, help="Path to StockData.csv")
    parser.add_argument("--pick-data-output", help="Pick-list CSV path for single-algorithm runs.")
    parser.add_argument("--alternative-locations-output", help="Alternative-locations CSV path for single-algorithm runs.")
    parser.add_argument("--output-dir", help="Directory for generated outputs. Used automatically with --algorithm all.")
    parser.add_argument("--floors", help="Comma-separated floor filter, e.g. MZN1,MZN2.")
    parser.add_argument("--articles", help="Comma-separated article filter.")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument(
        "--max-candidates-per-article",
        type=int,
        default=8,
        help="Keep only the best K GTSP candidates per article before the GTSP search. Use 0 or a negative value for all candidates.",
    )
    parser.add_argument("--iterations", type=int, default=250)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--route-estimator", choices=["insertion", "best_of_4"], default="insertion")
    parser.add_argument("--route-rebuild-threshold", type=int, default=60)
    parser.add_argument(
        "--search-objective-mode",
        choices=["construction", "primary"],
        default="construction",
        help="Objective used by the GTSP search itself. 'construction' is more warehouse-aware.",
    )
    parser.add_argument(
        "--search-route-estimator",
        choices=["insertion", "best_of_4"],
        default="insertion",
        help="Route estimator used inside the warehouse-aware GTSP search objective.",
    )

    parser.add_argument("--initial-temperature", type=float, default=10.0)
    parser.add_argument("--end-temperature", type=float, default=0.1)
    parser.add_argument("--cooling-rate", type=float, default=0.99)
    parser.add_argument("--inner-loops", type=int, default=50)

    parser.add_argument("--tabu-length", type=int)
    parser.add_argument("--neighborhood-size", type=int)

    parser.add_argument("--population", type=int, default=40)
    parser.add_argument("--cross-rate", type=float, default=0.8)
    parser.add_argument("--vary-rate", type=float, default=0.2)
    parser.add_argument("--elite-fraction", type=float, default=0.1)

    parser.add_argument("--colony-size", type=int, default=25)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--beta", type=float, default=2.0)
    parser.add_argument("--evaporation", type=float, default=0.35)
    parser.add_argument("--pheromone-q", type=float, default=100.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    floors = parse_floor_list(args.floors)
    articles = parse_article_list(args.articles)
    weights = ObjectiveWeights(
        distance=args.distance_weight,
        thm=args.thm_weight,
        floor=args.floor_weight,
    )
    candidate_cap = args.max_candidates_per_article
    if candidate_cap is not None and candidate_cap <= 0:
        candidate_cap = None

    try:
        adapter = WarehouseGTSPAdapter(
            args.orders,
            args.stock,
            floors=floors,
            articles=articles,
            weights=weights,
            max_candidates_per_article=candidate_cap,
            search_objective_mode=args.search_objective_mode,
            search_route_estimator=args.search_route_estimator,
        )
    except DataError as exc:
        parser.error(str(exc))
        return 2

    algorithm_names = list(ALGORITHMS) if args.algorithm == "all" else [args.algorithm]
    for offset, name in enumerate(algorithm_names):
        run_single_algorithm(name, adapter, args, seed_offset=offset)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

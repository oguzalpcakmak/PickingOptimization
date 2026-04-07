"""Large Neighborhood Search heuristic for warehouse picking.

This variant starts from a strong constructive seed and repeatedly applies a
fixed schedule of destroy/repair operators:
  1. close small THM clusters,
  2. rebuild route segments,
  3. rebuild floor slices,
  4. relocate random selected locations.

Each repair is validated with exact partial re-evaluation on the affected
floors only, then lightly intensified with the VNS local-descent moves.
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path
from typing import Sequence

from heuristic_common import (
    ObjectiveWeights,
    build_solution,
    parse_article_list,
    parse_floor_list,
    prepare_problem,
    print_report,
    write_alternative_locations_csv,
    write_pick_csv,
)
from neighborhood_search_common import (
    build_seed_state,
    destroy_floor_slice,
    destroy_light_thm_cluster,
    destroy_random_locations,
    destroy_route_cluster,
    repair_destroyed_subset,
)
from vns_heuristic import local_descent


DESTROY_OPERATORS = (
    ("light_thm_cluster", destroy_light_thm_cluster),
    ("route_cluster", destroy_route_cluster),
    ("floor_slice", destroy_floor_slice),
    ("random_locations", destroy_random_locations),
)


def solve(
    order_path: str | Path,
    stock_path: str | Path,
    *,
    floors: list[str] | None = None,
    articles: list[int] | None = None,
    distance_weight: float = 1.0,
    thm_weight: float = 15.0,
    floor_weight: float = 30.0,
    seed_mode: str = "fast_thm",
    time_limit: float = 20.0,
    iterations: int = 200,
    min_destroy_size: int = 2,
    max_destroy_size: int = 6,
    max_destroy_locations: int = 24,
    repair_target_limit: int = 6,
    seed_local_step_limit: int = 16,
    repair_intensify_steps: int = 6,
    source_sample_size: int = 48,
    target_sample_size: int = 6,
    thm_sample_size: int = 12,
    floor_sample_size: int = 4,
    max_locations_per_neighborhood: int = 10,
    restart_after: int = 16,
    candidate_pool_size: int = 6,
    seed: int = 7,
):
    total_start = time.perf_counter()
    phase_times: dict[str, float] = {}
    weights = ObjectiveWeights(distance=distance_weight, thm=thm_weight, floor=floor_weight)
    rng = random.Random(seed)

    step_start = time.perf_counter()
    demands, relevant_locs, loc_lookup, candidates_by_article = prepare_problem(
        order_path,
        stock_path,
        floors=floors,
        articles=articles,
    )
    phase_times["data_loading"] = time.perf_counter() - step_start
    print(
        f"  Data: {len(demands)} articles, {len(relevant_locs)} candidate locations "
        f"({phase_times['data_loading']:.2f}s)"
    )

    step_start = time.perf_counter()
    selected_seed, current_state = build_seed_state(
        seed_mode=seed_mode,
        demands=demands,
        relevant_locs=relevant_locs,
        loc_lookup=loc_lookup,
        candidates_by_article=candidates_by_article,
        weights=weights,
        seed=seed,
        candidate_pool_size=candidate_pool_size,
    )
    initial_seed_objective = current_state.objective_value
    phase_times["seed_construction"] = time.perf_counter() - step_start
    print(
        f"  Initial seed: {selected_seed}, objective={initial_seed_objective:.2f} "
        f"({phase_times['seed_construction']:.2f}s)"
    )

    deadline = None if time_limit <= 0 else (time.perf_counter() + time_limit)
    accepted_counts: dict[str, int] = {}

    seed_accepted = local_descent(
        current_state,
        candidates_by_article,
        rng=rng,
        deadline=deadline,
        source_sample_size=source_sample_size,
        target_sample_size=target_sample_size,
        thm_sample_size=thm_sample_size,
        floor_sample_size=floor_sample_size,
        max_locations_per_neighborhood=max_locations_per_neighborhood,
        local_step_limit=seed_local_step_limit,
        accepted_counts=accepted_counts,
    )
    if current_state.objective_value + 1e-9 < initial_seed_objective:
        print(
            f"  Seed local descent: {initial_seed_objective:.2f} -> "
            f"{current_state.objective_value:.2f} in {seed_accepted} accepted moves"
        )

    post_seed_local_objective = current_state.objective_value
    best_state = current_state.clone()
    search_start = time.perf_counter()
    iteration = 0
    best_iteration = 0
    improvements = 0
    accepted_destroy_counts: dict[str, int] = {}
    stall_count = 0

    destroy_span = max(1, max_destroy_size - min_destroy_size + 1)
    while iteration < max(1, iterations):
        if deadline is not None and time.perf_counter() >= deadline:
            break

        operator_name, operator = DESTROY_OPERATORS[iteration % len(DESTROY_OPERATORS)]
        destroy_size = min_destroy_size + (iteration % destroy_span)
        move = operator(
            current_state,
            rng=rng,
            destroy_size=destroy_size,
            max_locations=max_destroy_locations,
        )
        if move is None or not move.source_lids:
            iteration += 1
            continue

        candidate_state = repair_destroyed_subset(
            current_state,
            move,
            candidates_by_article,
            deadline=deadline,
            target_limit=max(2, repair_target_limit + (iteration % 2)),
            intensify_steps=repair_intensify_steps,
            rng=rng,
            source_sample_size=source_sample_size,
            target_sample_size=target_sample_size,
            thm_sample_size=thm_sample_size,
            floor_sample_size=floor_sample_size,
            max_locations_per_neighborhood=max_locations_per_neighborhood,
        )
        iteration += 1
        if candidate_state is None:
            stall_count += 1
            if stall_count >= restart_after:
                current_state = best_state.clone()
                stall_count = 0
            continue

        if candidate_state.objective_value + 1e-9 < best_state.objective_value:
            print(
                f"  LNS improvement {iteration}: {best_state.objective_value:.2f} -> "
                f"{candidate_state.objective_value:.2f} via {operator_name}"
            )
            best_state = candidate_state.clone()
            current_state = candidate_state
            best_iteration = iteration
            improvements += 1
            accepted_destroy_counts[move.name] = accepted_destroy_counts.get(move.name, 0) + 1
            stall_count = 0
            continue

        if candidate_state.objective_value + 1e-9 < current_state.objective_value:
            current_state = candidate_state
            accepted_destroy_counts[move.name] = accepted_destroy_counts.get(move.name, 0) + 1
            stall_count = max(0, stall_count - 1)
            continue

        stall_count += 1
        if stall_count >= restart_after:
            current_state = best_state.clone()
            stall_count = 0

    phase_times["lns_search"] = time.perf_counter() - search_start

    step_start = time.perf_counter()
    solution = build_solution(
        algorithm="Large Neighborhood Search Heuristic",
        picks_by_location=best_state.picks_by_location,
        demands=demands,
        relevant_locs=relevant_locs,
        loc_lookup=loc_lookup,
        weights=weights,
        solve_time=0.0,
        phase_times={},
        notes={
            "seed_mode": seed_mode,
            "selected_seed": selected_seed,
            "initial_seed_objective": f"{initial_seed_objective:.2f}",
            "post_seed_local_objective": f"{post_seed_local_objective:.2f}",
            "iterations_run": iteration,
            "best_iteration": best_iteration if best_iteration > 0 else "seed",
            "improvements": improvements,
            "destroy_schedule": "light_thm -> route_cluster -> floor_slice -> random",
            "accepted_light_thm_cluster": accepted_destroy_counts.get("light_thm_cluster", 0),
            "accepted_route_cluster": accepted_destroy_counts.get("route_cluster", 0),
            "accepted_floor_slice": accepted_destroy_counts.get("floor_slice", 0),
            "accepted_random_locations": accepted_destroy_counts.get("random_locations", 0),
        },
        route_hints_by_floor=best_state.route_by_floor,
    )
    phase_times["final_route_rebuild"] = time.perf_counter() - step_start

    solve_time = time.perf_counter() - total_start
    phase_times["total"] = solve_time
    solution.solve_time = solve_time
    solution.phase_times = dict(phase_times)
    return solution


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Large Neighborhood Search heuristic for warehouse picking.")
    parser.add_argument("--orders", default="PickOrder.csv")
    parser.add_argument("--stock", default="StockData.csv")
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument("--seed-mode", choices=("fast_thm", "regret", "best"), default="fast_thm")
    parser.add_argument("--time-limit", type=float, default=20.0, help="Search time budget in seconds. Use 0 for no cap.")
    parser.add_argument("--iterations", type=int, default=200, help="Maximum number of destroy/repair iterations.")
    parser.add_argument("--min-destroy-size", type=int, default=2)
    parser.add_argument("--max-destroy-size", type=int, default=6)
    parser.add_argument("--max-destroy-locations", type=int, default=24)
    parser.add_argument("--repair-target-limit", type=int, default=6)
    parser.add_argument("--seed-local-step-limit", type=int, default=16)
    parser.add_argument("--repair-intensify-steps", type=int, default=6)
    parser.add_argument("--source-sample-size", type=int, default=48)
    parser.add_argument("--target-sample-size", type=int, default=6)
    parser.add_argument("--thm-sample-size", type=int, default=12)
    parser.add_argument("--floor-sample-size", type=int, default=4)
    parser.add_argument("--max-locations-per-neighborhood", type=int, default=10)
    parser.add_argument("--restart-after", type=int, default=16)
    parser.add_argument("--candidate-pool-size", type=int, default=6)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--output",
        "--pick-data-output",
        dest="pick_data_output",
        default="PickDataOutput_LNS.csv",
        help="Pick CSV output path.",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput_LNS.csv",
        help="Alternative locations CSV output path. Pass empty string to disable.",
    )
    args = parser.parse_args(argv)

    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  LARGE NEIGHBORHOOD SEARCH HEURISTIC                             ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()

    floors = parse_floor_list(args.floors)
    articles = parse_article_list(args.articles)
    solution = solve(
        args.orders,
        args.stock,
        floors=floors,
        articles=articles,
        distance_weight=args.distance_weight,
        thm_weight=args.thm_weight,
        floor_weight=args.floor_weight,
        seed_mode=args.seed_mode,
        time_limit=args.time_limit,
        iterations=args.iterations,
        min_destroy_size=args.min_destroy_size,
        max_destroy_size=args.max_destroy_size,
        max_destroy_locations=args.max_destroy_locations,
        repair_target_limit=args.repair_target_limit,
        seed_local_step_limit=args.seed_local_step_limit,
        repair_intensify_steps=args.repair_intensify_steps,
        source_sample_size=args.source_sample_size,
        target_sample_size=args.target_sample_size,
        thm_sample_size=args.thm_sample_size,
        floor_sample_size=args.floor_sample_size,
        max_locations_per_neighborhood=args.max_locations_per_neighborhood,
        restart_after=args.restart_after,
        candidate_pool_size=args.candidate_pool_size,
        seed=args.seed,
    )
    print_report(solution)

    if args.pick_data_output:
        output_path = write_pick_csv(solution, args.pick_data_output)
        print(f"\nPick output written to {output_path}")
    if args.alternative_locations_output:
        alternative_path = write_alternative_locations_csv(solution, args.alternative_locations_output)
        print(f"Alternative locations written to {alternative_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

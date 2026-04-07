"""Adaptive Large Neighborhood Search heuristic for warehouse picking.

This variant reuses the same destroy/repair neighborhoods as the plain LNS
solver, but adaptively reweights destroy and repair operators based on their
observed contribution during search.
"""

from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class RepairOperator:
    name: str
    target_limit: int
    intensify_steps: int


DESTROY_OPERATORS = {
    "light_thm_cluster": destroy_light_thm_cluster,
    "route_cluster": destroy_route_cluster,
    "floor_slice": destroy_floor_slice,
    "random_locations": destroy_random_locations,
}

REPAIR_OPERATORS = {
    "compact": RepairOperator(name="compact", target_limit=4, intensify_steps=0),
    "balanced": RepairOperator(name="balanced", target_limit=6, intensify_steps=4),
    "deep": RepairOperator(name="deep", target_limit=10, intensify_steps=8),
}


def roulette_choice(weights: dict[str, float], rng: random.Random) -> str:
    names = list(weights)
    values = [max(1e-6, weights[name]) for name in names]
    return rng.choices(names, weights=values, k=1)[0]


def update_weights(
    weights: dict[str, float],
    scores: dict[str, float],
    usage: dict[str, int],
    *,
    reaction_factor: float,
) -> None:
    for name in weights:
        if usage[name] > 0:
            observed = scores[name] / usage[name]
            weights[name] = max(0.1, (1.0 - reaction_factor) * weights[name] + reaction_factor * observed)
        scores[name] = 0.0
        usage[name] = 0


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
    iterations: int = 250,
    min_destroy_size: int = 2,
    max_destroy_size: int = 7,
    max_destroy_locations: int = 28,
    seed_local_step_limit: int = 16,
    source_sample_size: int = 48,
    target_sample_size: int = 6,
    thm_sample_size: int = 12,
    floor_sample_size: int = 4,
    max_locations_per_neighborhood: int = 10,
    segment_length: int = 20,
    reaction_factor: float = 0.35,
    soft_accept_relaxation: float = 0.003,
    soft_accept_probability: float = 0.10,
    restart_after: int = 24,
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

    destroy_weights = {name: 1.0 for name in DESTROY_OPERATORS}
    repair_weights = {name: 1.0 for name in REPAIR_OPERATORS}
    destroy_scores = {name: 0.0 for name in DESTROY_OPERATORS}
    repair_scores = {name: 0.0 for name in REPAIR_OPERATORS}
    destroy_usage = {name: 0 for name in DESTROY_OPERATORS}
    repair_usage = {name: 0 for name in REPAIR_OPERATORS}

    accepted_destroy_counts = {name: 0 for name in DESTROY_OPERATORS}
    accepted_repair_counts = {name: 0 for name in REPAIR_OPERATORS}
    iteration = 0
    improvements = 0
    best_iteration = 0
    soft_accepts = 0
    stall_count = 0
    destroy_span = max(1, max_destroy_size - min_destroy_size + 1)

    while iteration < max(1, iterations):
        if deadline is not None and time.perf_counter() >= deadline:
            break

        destroy_name = roulette_choice(destroy_weights, rng)
        repair_name = roulette_choice(repair_weights, rng)
        destroy_operator = DESTROY_OPERATORS[destroy_name]
        repair_operator = REPAIR_OPERATORS[repair_name]
        destroy_size = min_destroy_size + (iteration % destroy_span)

        move = destroy_operator(
            current_state,
            rng=rng,
            destroy_size=destroy_size,
            max_locations=max_destroy_locations,
        )
        destroy_usage[destroy_name] += 1
        repair_usage[repair_name] += 1
        iteration += 1

        if move is None or not move.source_lids:
            continue

        candidate_state = repair_destroyed_subset(
            current_state,
            move,
            candidates_by_article,
            deadline=deadline,
            target_limit=repair_operator.target_limit,
            intensify_steps=repair_operator.intensify_steps,
            rng=rng,
            source_sample_size=source_sample_size,
            target_sample_size=target_sample_size,
            thm_sample_size=thm_sample_size,
            floor_sample_size=floor_sample_size,
            max_locations_per_neighborhood=max_locations_per_neighborhood,
        )

        reward = 0.0
        accepted = False
        if candidate_state is not None:
            if candidate_state.objective_value + 1e-9 < best_state.objective_value:
                print(
                    f"  ALNS improvement {iteration}: {best_state.objective_value:.2f} -> "
                    f"{candidate_state.objective_value:.2f} via {destroy_name} + {repair_name}"
                )
                best_state = candidate_state.clone()
                current_state = candidate_state
                best_iteration = iteration
                improvements += 1
                reward = 6.0
                accepted = True
                stall_count = 0
            elif candidate_state.objective_value + 1e-9 < current_state.objective_value:
                current_state = candidate_state
                reward = 3.0
                accepted = True
                stall_count = max(0, stall_count - 1)
            elif (
                soft_accept_relaxation > 0
                and candidate_state.objective_value <= current_state.objective_value * (1.0 + soft_accept_relaxation)
                and rng.random() < soft_accept_probability
            ):
                current_state = candidate_state
                reward = 1.0
                accepted = True
                soft_accepts += 1
                stall_count += 1
            else:
                reward = 0.2
                stall_count += 1
        else:
            stall_count += 1

        destroy_scores[destroy_name] += reward
        repair_scores[repair_name] += reward
        if accepted:
            accepted_destroy_counts[destroy_name] += 1
            accepted_repair_counts[repair_name] += 1

        if segment_length > 0 and iteration % segment_length == 0:
            update_weights(
                destroy_weights,
                destroy_scores,
                destroy_usage,
                reaction_factor=reaction_factor,
            )
            update_weights(
                repair_weights,
                repair_scores,
                repair_usage,
                reaction_factor=reaction_factor,
            )

        if stall_count >= restart_after:
            current_state = best_state.clone()
            stall_count = 0

    phase_times["alns_search"] = time.perf_counter() - search_start

    step_start = time.perf_counter()
    solution = build_solution(
        algorithm="Adaptive Large Neighborhood Search Heuristic",
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
            "soft_accepts": soft_accepts,
            "destroy_weights": ", ".join(f"{name}={destroy_weights[name]:.2f}" for name in sorted(destroy_weights)),
            "repair_weights": ", ".join(f"{name}={repair_weights[name]:.2f}" for name in sorted(repair_weights)),
            "accepted_light_thm_cluster": accepted_destroy_counts.get("light_thm_cluster", 0),
            "accepted_route_cluster": accepted_destroy_counts.get("route_cluster", 0),
            "accepted_floor_slice": accepted_destroy_counts.get("floor_slice", 0),
            "accepted_random_locations": accepted_destroy_counts.get("random_locations", 0),
            "accepted_compact_repairs": accepted_repair_counts.get("compact", 0),
            "accepted_balanced_repairs": accepted_repair_counts.get("balanced", 0),
            "accepted_deep_repairs": accepted_repair_counts.get("deep", 0),
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
    parser = argparse.ArgumentParser(description="Adaptive Large Neighborhood Search heuristic for warehouse picking.")
    parser.add_argument("--orders", default="PickOrder.csv")
    parser.add_argument("--stock", default="StockData.csv")
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument("--seed-mode", choices=("fast_thm", "regret", "best"), default="fast_thm")
    parser.add_argument("--time-limit", type=float, default=20.0, help="Search time budget in seconds. Use 0 for no cap.")
    parser.add_argument("--iterations", type=int, default=250, help="Maximum number of ALNS iterations.")
    parser.add_argument("--min-destroy-size", type=int, default=2)
    parser.add_argument("--max-destroy-size", type=int, default=7)
    parser.add_argument("--max-destroy-locations", type=int, default=28)
    parser.add_argument("--seed-local-step-limit", type=int, default=16)
    parser.add_argument("--source-sample-size", type=int, default=48)
    parser.add_argument("--target-sample-size", type=int, default=6)
    parser.add_argument("--thm-sample-size", type=int, default=12)
    parser.add_argument("--floor-sample-size", type=int, default=4)
    parser.add_argument("--max-locations-per-neighborhood", type=int, default=10)
    parser.add_argument("--segment-length", type=int, default=20, help="ALNS weight-update segment length.")
    parser.add_argument("--reaction-factor", type=float, default=0.35, help="Weight adaptation aggressiveness in [0,1].")
    parser.add_argument("--soft-accept-relaxation", type=float, default=0.003, help="Relative objective slack allowed for soft acceptance.")
    parser.add_argument("--soft-accept-probability", type=float, default=0.10, help="Probability of accepting a near-tie candidate.")
    parser.add_argument("--restart-after", type=int, default=24)
    parser.add_argument("--candidate-pool-size", type=int, default=6)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--output",
        "--pick-data-output",
        dest="pick_data_output",
        default="PickDataOutput_ALNS.csv",
        help="Pick CSV output path.",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput_ALNS.csv",
        help="Alternative locations CSV output path. Pass empty string to disable.",
    )
    args = parser.parse_args(argv)

    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  ADAPTIVE LARGE NEIGHBORHOOD SEARCH HEURISTIC                    ║")
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
        seed_local_step_limit=args.seed_local_step_limit,
        source_sample_size=args.source_sample_size,
        target_sample_size=args.target_sample_size,
        thm_sample_size=args.thm_sample_size,
        floor_sample_size=args.floor_sample_size,
        max_locations_per_neighborhood=args.max_locations_per_neighborhood,
        segment_length=args.segment_length,
        reaction_factor=args.reaction_factor,
        soft_accept_relaxation=args.soft_accept_relaxation,
        soft_accept_probability=args.soft_accept_probability,
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

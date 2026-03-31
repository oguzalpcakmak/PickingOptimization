"""GRASP-style multi-start heuristic for warehouse picking.

This solver reuses the same exact-style distance accounting as the deterministic
heuristic, but randomizes both article selection and location selection through
restricted candidate lists (RCLs). Each iteration:
  1. builds a feasible picking plan with randomized greedy choices,
  2. rebuilds floor routes with regret insertion + 2-opt,
  3. keeps the best solution found across all iterations.

The implementation favors short iteration times so the user can scale quality
by increasing the iteration count or time limit.
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path
from typing import Sequence

from heuristic_common import (
    CandidateScore,
    ConstructionState,
    DataError,
    ObjectiveWeights,
    build_rcl,
    build_solution,
    candidate_sort_key,
    compute_article_order,
    parse_article_list,
    parse_floor_list,
    prepare_problem,
    print_report,
    write_alternative_locations_csv,
    write_pick_csv,
)


def choose_from_rcl(rcl: Sequence[CandidateScore], rng: random.Random) -> CandidateScore:
    if not rcl:
        raise DataError("Cannot choose from an empty restricted candidate list.")
    if len(rcl) == 1:
        return rcl[0]
    weights = list(range(len(rcl), 0, -1))
    return rng.choices(list(rcl), weights=weights, k=1)[0]


def choose_randomized_candidate(
    article: int,
    remaining_demand: int,
    candidates_by_article,
    state: ConstructionState,
    *,
    alpha: float,
    location_rcl_size: int,
    rng: random.Random,
    deterministic: bool = False,
) -> CandidateScore:
    scored = []
    for loc in candidates_by_article[article]:
        candidate = state.evaluate_candidate(loc, remaining_demand)
        if candidate is not None:
            scored.append(candidate)
    if not scored:
        raise DataError(f"Article {article} still has demand {remaining_demand}, but no feasible stock remains.")
    scored.sort(key=candidate_sort_key)
    if deterministic:
        return scored[0]
    rcl = build_rcl(scored, alpha=alpha, max_size=location_rcl_size)
    return choose_from_rcl(rcl, rng)


def construct_once(
    demands,
    article_order,
    candidates_by_article,
    loc_lookup,
    weights: ObjectiveWeights,
    *,
    alpha: float,
    article_rcl_size: int,
    location_rcl_size: int,
    rng: random.Random,
    deterministic: bool = False,
) -> tuple[ConstructionState, float]:
    start = time.perf_counter()
    state = ConstructionState(loc_lookup, weights)
    remaining_articles = list(article_order)

    while remaining_articles:
        limit = 1 if deterministic else max(1, min(article_rcl_size, len(remaining_articles)))
        article_index = 0 if deterministic else rng.randrange(limit)
        article = remaining_articles.pop(article_index)

        remaining = demands[article]
        while remaining > 0:
            choice = choose_randomized_candidate(
                article,
                remaining,
                candidates_by_article,
                state,
                alpha=alpha,
                location_rcl_size=location_rcl_size,
                rng=rng,
                deterministic=deterministic,
            )
            state.commit(choice)
            remaining -= choice.take

    return state, time.perf_counter() - start


def solve(
    order_path: str | Path,
    stock_path: str | Path,
    *,
    floors: list[str] | None = None,
    articles: list[int] | None = None,
    distance_weight: float = 1.0,
    thm_weight: float = 15.0,
    floor_weight: float = 30.0,
    iterations: int = 25,
    time_limit: float = 10.0,
    alpha: float = 0.25,
    article_rcl_size: int = 6,
    location_rcl_size: int = 5,
    seed: int = 7,
):
    total_start = time.perf_counter()
    phase_times: dict[str, float] = {}
    weights = ObjectiveWeights(distance=distance_weight, thm=thm_weight, floor=floor_weight)

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
    base_order = compute_article_order(demands, candidates_by_article, weights)
    phase_times["article_ordering"] = time.perf_counter() - step_start
    print(
        f"  Base priority queue built for {len(base_order)} articles "
        f"({phase_times['article_ordering']:.2f}s)"
    )

    rng = random.Random(seed)
    search_start = time.perf_counter()
    deadline = None if time_limit <= 0 else (search_start + time_limit)

    best_solution = None
    best_objective = float("inf")
    best_iteration = 0
    best_construction_time = 0.0
    best_route_time = 0.0
    completed_iterations = 0

    max_iterations = max(1, iterations)
    while completed_iterations < max_iterations:
        if completed_iterations > 0 and deadline is not None and time.perf_counter() >= deadline:
            break

        iteration_number = completed_iterations + 1
        deterministic_iteration = iteration_number == 1
        iteration_start = time.perf_counter()

        state, construction_time = construct_once(
            demands,
            base_order,
            candidates_by_article,
            loc_lookup,
            weights,
            alpha=alpha,
            article_rcl_size=article_rcl_size,
            location_rcl_size=location_rcl_size,
            rng=rng,
            deterministic=deterministic_iteration,
        )

        route_start = time.perf_counter()
        candidate_solution = build_solution(
            algorithm="GRASP Multi-Start Heuristic",
            picks_by_location=state.picks_by_location,
            demands=demands,
            relevant_locs=relevant_locs,
            loc_lookup=loc_lookup,
            weights=weights,
            solve_time=0.0,
            phase_times={},
            notes={},
            route_hints_by_floor=dict(state.route_by_floor),
        )
        route_time = time.perf_counter() - route_start
        iteration_time = time.perf_counter() - iteration_start
        completed_iterations += 1

        if candidate_solution.objective_value + 1e-9 < best_objective:
            best_solution = candidate_solution
            best_objective = candidate_solution.objective_value
            best_iteration = iteration_number
            best_construction_time = construction_time
            best_route_time = route_time
            print(
                f"  Iteration {iteration_number}{' (elite seed)' if deterministic_iteration else ''}: "
                f"new best objective={best_objective:.2f} "
                f"({iteration_time:.2f}s)"
            )
        elif iteration_number == 1 or iteration_number % 5 == 0:
            print(
                f"  Iteration {iteration_number}{' (elite seed)' if deterministic_iteration else ''}: "
                f"objective={candidate_solution.objective_value:.2f} "
                f"({iteration_time:.2f}s)"
            )

    phase_times["multistart_search"] = time.perf_counter() - search_start
    solve_time = time.perf_counter() - total_start
    phase_times["best_construction"] = best_construction_time
    phase_times["best_route_rebuild"] = best_route_time
    phase_times["total"] = solve_time

    if best_solution is None:
        raise DataError("GRASP search did not produce a feasible solution.")

    best_solution.solve_time = solve_time
    best_solution.phase_times = dict(phase_times)
    best_solution.notes.update(
        {
            "best_iteration": best_iteration,
            "iterations_run": completed_iterations,
            "seed": seed,
            "rcl_alpha": f"{alpha:.2f}",
            "article_rcl_size": article_rcl_size,
            "location_rcl_size": location_rcl_size,
            "elite_seed": "deterministic iteration 1",
        }
    )
    return best_solution


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GRASP multi-start heuristic for warehouse picking.")
    parser.add_argument("--orders", default="PickOrder.csv")
    parser.add_argument("--stock", default="StockData.csv")
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument("--iterations", type=int, default=25, help="Maximum number of GRASP iterations.")
    parser.add_argument("--time-limit", type=float, default=10.0, help="Search time budget in seconds.")
    parser.add_argument("--alpha", type=float, default=0.25, help="RCL threshold parameter in [0, 1].")
    parser.add_argument("--article-rcl-size", type=int, default=6, help="Randomize next article among this many top-priority articles.")
    parser.add_argument("--location-rcl-size", type=int, default=5, help="Randomize next location among this many best-scoring locations.")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--output",
        "--pick-data-output",
        dest="pick_data_output",
        default="PickDataOutput_GRASP.csv",
        help="Pick CSV output path.",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput_GRASP.csv",
        help="Alternative locations CSV output path. Pass empty string to disable.",
    )
    args = parser.parse_args(argv)

    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  GRASP MULTI-START HEURISTIC                                     ║")
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
        iterations=args.iterations,
        time_limit=args.time_limit,
        alpha=args.alpha,
        article_rcl_size=args.article_rcl_size,
        location_rcl_size=args.location_rcl_size,
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

"""Fast THM-first heuristic with S-shape routing.

This variant is designed for full-data practicality:
  1. Build a THM cover quickly with an incremental greedy scorer.
  2. Prune redundant THMs with a fast coverage check.
  3. Repeat the greedy construction for a few multi-start iterations.
  4. Allocate picks inside the selected THMs and route each floor with
     S-shape routing.

Unlike the exact-style THM-min solvers, this heuristic does not try to prove
absolute minimum THM cardinality. It aims for a strong THM-first solution in
seconds rather than an exact cover proof that can take minutes or hours.
"""

from __future__ import annotations

import argparse
import heapq
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from heuristic_common import (
    DataError,
    ObjectiveWeights,
    floor_index,
    parse_article_list,
    parse_floor_list,
    prepare_problem,
    print_report,
    write_alternative_locations_csv,
    write_pick_csv,
)
from thm_min_rr_heuristic import (
    THMOption,
    allocate_within_selected_thms,
    build_article_candidates,
    group_thm_options,
    selected_locations,
)
from thm_min_s_shape_heuristic import build_solution_from_s_shape


def _push_heap_entry(
    heap: list[tuple[Any, ...]],
    *,
    thm_id: str,
    score_by_thm: dict[str, int],
    article_count_by_thm: dict[str, int],
    version_by_thm: dict[str, int],
    thm_options: dict[str, THMOption],
) -> None:
    option = thm_options[thm_id]
    score = score_by_thm.get(thm_id, 0)
    article_count = article_count_by_thm.get(thm_id, 0)
    heapq.heappush(
        heap,
        (
            -score,
            -article_count,
            floor_index(option.floor),
            option.aisle,
            option.column,
            thm_id,
            version_by_thm[thm_id],
        ),
    )


def initialize_fast_scores(
    demands: dict[int, int],
    thm_options: dict[str, THMOption],
) -> tuple[dict[str, int], dict[str, int]]:
    score_by_thm: dict[str, int] = {}
    article_count_by_thm: dict[str, int] = {}
    relevant_articles = set(demands)
    for thm_id, option in thm_options.items():
        score = 0
        article_count = 0
        for article, cap in option.capacities.items():
            if article not in relevant_articles:
                continue
            effective = min(demands[article], cap)
            if effective > 0:
                score += effective
                article_count += 1
        score_by_thm[thm_id] = score
        article_count_by_thm[thm_id] = article_count
    return score_by_thm, article_count_by_thm


def pop_top_candidates(
    heap: list[tuple[Any, ...]],
    *,
    available: set[str],
    score_by_thm: dict[str, int],
    version_by_thm: dict[str, int],
    limit: int,
) -> list[tuple[Any, ...]]:
    top: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    while heap and len(top) < limit:
        entry = heapq.heappop(heap)
        thm_id = entry[5]
        version = entry[6]
        if thm_id not in available:
            continue
        if version != version_by_thm[thm_id]:
            continue
        if score_by_thm.get(thm_id, 0) <= 0:
            continue
        if thm_id in seen:
            continue
        seen.add(thm_id)
        top.append(entry)
    return top


def choose_candidate(
    top_candidates: list[tuple[Any, ...]],
    *,
    rng: random.Random,
    deterministic: bool,
) -> tuple[Any, ...]:
    if not top_candidates:
        raise DataError("Fast THM-first search ran out of positive-coverage candidates.")
    if deterministic or len(top_candidates) == 1:
        return top_candidates[0]
    weights = list(range(len(top_candidates), 0, -1))
    index = rng.choices(range(len(top_candidates)), weights=weights, k=1)[0]
    return top_candidates[index]


def greedy_cover_fast(
    demands: dict[int, int],
    thm_options: dict[str, THMOption],
    article_candidates: dict[int, list[str]],
    *,
    rng: random.Random,
    deterministic: bool,
    candidate_pool_size: int,
) -> list[str]:
    remaining = dict(demands)
    available = set(thm_options)
    score_by_thm, article_count_by_thm = initialize_fast_scores(demands, thm_options)
    version_by_thm = {thm_id: 0 for thm_id in thm_options}

    heap: list[tuple[Any, ...]] = []
    for thm_id in thm_options:
        if score_by_thm[thm_id] > 0:
            _push_heap_entry(
                heap,
                thm_id=thm_id,
                score_by_thm=score_by_thm,
                article_count_by_thm=article_count_by_thm,
                version_by_thm=version_by_thm,
                thm_options=thm_options,
            )

    selected: list[str] = []
    limit = max(1, candidate_pool_size)
    while remaining:
        top_candidates = pop_top_candidates(
            heap,
            available=available,
            score_by_thm=score_by_thm,
            version_by_thm=version_by_thm,
            limit=limit,
        )
        chosen = choose_candidate(top_candidates, rng=rng, deterministic=deterministic)
        chosen_thm = chosen[5]

        for entry in top_candidates:
            if entry[5] != chosen_thm:
                heapq.heappush(heap, entry)

        if chosen_thm not in available:
            raise DataError(f"Chosen THM {chosen_thm} is no longer available.")

        selected.append(chosen_thm)
        available.remove(chosen_thm)

        option = thm_options[chosen_thm]
        for article, cap in option.capacities.items():
            old_remaining = remaining.get(article, 0)
            if old_remaining <= 0:
                continue
            new_remaining = max(0, old_remaining - cap)
            if new_remaining == old_remaining:
                continue

            if new_remaining == 0:
                remaining.pop(article, None)
            else:
                remaining[article] = new_remaining

            for other_thm in article_candidates[article]:
                if other_thm not in available:
                    continue
                other_cap = thm_options[other_thm].capacities.get(article, 0)
                if other_cap <= 0:
                    continue

                old_effective = min(old_remaining, other_cap)
                new_effective = min(new_remaining, other_cap)
                score_by_thm[other_thm] -= old_effective - new_effective
                if old_remaining > 0 and new_remaining == 0 and old_effective > 0:
                    article_count_by_thm[other_thm] -= 1

                version_by_thm[other_thm] += 1
                if score_by_thm[other_thm] > 0:
                    _push_heap_entry(
                        heap,
                        thm_id=other_thm,
                        score_by_thm=score_by_thm,
                        article_count_by_thm=article_count_by_thm,
                        version_by_thm=version_by_thm,
                        thm_options=thm_options,
                    )

    return selected


def fast_prune_redundant_thms(
    demands: dict[int, int],
    selected_thms: list[str],
    thm_options: dict[str, THMOption],
) -> list[str]:
    current = list(dict.fromkeys(selected_thms))
    cover: dict[int, int] = defaultdict(int)
    for thm_id in current:
        for article, cap in thm_options[thm_id].capacities.items():
            if article in demands:
                cover[article] += cap

    def removable_key(thm_id: str) -> tuple[Any, ...]:
        option = thm_options[thm_id]
        tight_articles = 0
        total_effective = 0
        for article, cap in option.capacities.items():
            demand = demands.get(article)
            if demand is None:
                continue
            residual = cover[article] - cap - demand
            if residual < 0:
                tight_articles += 1
            total_effective += min(demand, cap)
        return (
            tight_articles,
            total_effective,
            floor_index(option.floor),
            option.aisle,
            option.column,
            thm_id,
        )

    changed = True
    while changed:
        changed = False
        for thm_id in sorted(current, key=removable_key):
            option = thm_options[thm_id]
            feasible = True
            for article, cap in option.capacities.items():
                demand = demands.get(article)
                if demand is None:
                    continue
                if cover[article] - cap < demand:
                    feasible = False
                    break
            if not feasible:
                continue
            current.remove(thm_id)
            for article, cap in option.capacities.items():
                if article in demands:
                    cover[article] -= cap
            changed = True
            break

    return current


def selection_tie_key(selected_thms: list[str], thm_options: dict[str, THMOption]) -> tuple[Any, ...]:
    floors = {thm_options[thm_id].floor for thm_id in selected_thms}
    nodes = {thm_options[thm_id].node_key for thm_id in selected_thms}
    return (
        len(selected_thms),
        len(floors),
        len(nodes),
        tuple(
            (
                floor_index(thm_options[thm_id].floor),
                thm_options[thm_id].aisle,
                thm_options[thm_id].column,
                thm_id,
            )
            for thm_id in sorted(selected_thms)
        ),
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
    iterations: int = 12,
    time_limit: float = 10.0,
    candidate_pool_size: int = 6,
    seed: int = 7,
):
    total_start = time.perf_counter()
    phase_times: dict[str, float] = {}
    weights = ObjectiveWeights(distance=distance_weight, thm=thm_weight, floor=floor_weight)

    step_start = time.perf_counter()
    demands, relevant_locs, loc_lookup, _ = prepare_problem(
        order_path,
        stock_path,
        floors=floors,
        articles=articles,
    )
    thm_options = group_thm_options(relevant_locs)
    article_candidates = build_article_candidates(demands, thm_options)
    phase_times["data_loading"] = time.perf_counter() - step_start
    print(
        f"  Data: {len(demands)} articles, {len(relevant_locs)} candidate locations, "
        f"{len(thm_options)} candidate THMs ({phase_times['data_loading']:.2f}s)"
    )

    rng = random.Random(seed)
    search_start = time.perf_counter()
    deadline = None if time_limit <= 0 else search_start + time_limit

    best_solution = None
    best_selection: list[str] | None = None
    best_key = None
    best_iteration = 0
    completed_iterations = 0
    best_selection_time = 0.0
    best_routing_time = 0.0

    while completed_iterations < max(1, iterations):
        if completed_iterations > 0 and deadline is not None and time.perf_counter() >= deadline:
            break

        iteration_number = completed_iterations + 1
        deterministic_iteration = iteration_number == 1
        iteration_start = time.perf_counter()

        selection_start = time.perf_counter()
        selection = greedy_cover_fast(
            demands,
            thm_options,
            article_candidates,
            rng=rng,
            deterministic=deterministic_iteration,
            candidate_pool_size=candidate_pool_size,
        )
        selection = fast_prune_redundant_thms(demands, selection, thm_options)
        selection_time = time.perf_counter() - selection_start

        routing_start = time.perf_counter()
        picks_by_location = allocate_within_selected_thms(demands, selection, loc_lookup, thm_options)
        candidate_solution = build_solution_from_s_shape(
            picks_by_location=picks_by_location,
            demands=demands,
            relevant_locs=selected_locations(selection, loc_lookup, thm_options),
            loc_lookup=loc_lookup,
            weights=weights,
            solve_time=0.0,
            phase_times={},
            notes={},
        )
        routing_time = time.perf_counter() - routing_start

        completed_iterations += 1
        selection_key = selection_tie_key(selection, thm_options)
        solution_key = (
            candidate_solution.total_thms,
            candidate_solution.total_distance,
            candidate_solution.total_floors,
            candidate_solution.total_picks,
            selection_key,
        )

        if best_key is None or solution_key < best_key:
            best_key = solution_key
            best_selection = list(selection)
            best_solution = candidate_solution
            best_iteration = iteration_number
            best_selection_time = selection_time
            best_routing_time = routing_time
            print(
                f"  Iteration {iteration_number}{' (elite seed)' if deterministic_iteration else ''}: "
                f"new best thms={candidate_solution.total_thms}, "
                f"objective={candidate_solution.objective_value:.2f} "
                f"({time.perf_counter() - iteration_start:.2f}s)"
            )
        elif iteration_number == 1 or iteration_number % 5 == 0:
            print(
                f"  Iteration {iteration_number}{' (elite seed)' if deterministic_iteration else ''}: "
                f"thms={candidate_solution.total_thms}, "
                f"objective={candidate_solution.objective_value:.2f} "
                f"({time.perf_counter() - iteration_start:.2f}s)"
            )

    if best_solution is None or best_selection is None:
        raise DataError("Fast THM-first S-shape heuristic did not produce a feasible solution.")

    phase_times["multistart_search"] = time.perf_counter() - search_start
    solve_time = time.perf_counter() - total_start
    phase_times["best_selection"] = best_selection_time
    phase_times["best_allocation_and_routing"] = best_routing_time
    phase_times["total"] = solve_time

    best_solution.solve_time = solve_time
    best_solution.phase_times = dict(phase_times)
    best_solution.notes.update(
        {
            "phase_1_goal": "fast THM-first greedy cover",
            "routing": "S-shape aisle routing",
            "best_iteration": best_iteration,
            "iterations_run": completed_iterations,
            "seed": seed,
            "candidate_pool_size": candidate_pool_size,
            "selection_mode": "deterministic seed + randomized top-k restarts",
            "thm_count_not_proven": "heuristic only",
            "selected_thm_count": len(best_selection),
        }
    )
    return best_solution


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fast THM-first heuristic with S-shape routing.")
    parser.add_argument("--orders", default="data/full/PickOrder.csv")
    parser.add_argument("--stock", default="data/full/StockData.csv")
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument("--iterations", type=int, default=12, help="Maximum number of fast multi-start iterations.")
    parser.add_argument("--time-limit", type=float, default=10.0, help="Search time budget in seconds. Use 0 for no cap.")
    parser.add_argument("--candidate-pool-size", type=int, default=6, help="Randomize among this many top THM candidates after the elite seed iteration.")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--output",
        "--pick-data-output",
        dest="pick_data_output",
        default="PickDataOutput_FastTHMFirstSShape.csv",
        help="Pick CSV output path.",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput_FastTHMFirstSShape.csv",
        help="Alternative locations CSV output path. Pass empty string to disable.",
    )
    args = parser.parse_args(argv)

    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  FAST THM-FIRST + S-SHAPE HEURISTIC                              ║")
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

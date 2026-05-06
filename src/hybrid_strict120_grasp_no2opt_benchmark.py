"""Hybrid full-data benchmark:
1) 120s strict insertion prepass with open-THM short-circuit
2) GRASP residual completion without final 2-opt

This script is intended for reproducible benchmarking of the hybrid idea
discussed in the full-data analysis.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Sequence

from grasp_heuristic import choose_randomized_candidate
from heuristic_common import (
    ConstructionState,
    Loc,
    ObjectiveWeights,
    build_solution,
    candidate_sort_key,
    compute_article_order,
    prepare_problem,
    route_cost,
    write_alternative_locations_csv,
    write_pick_csv,
)


class _CandidateWrapper:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


def _strict_best_position_cost(route, node):
    if not route:
        new_route = [node]
        return route_cost(new_route), 0, new_route

    best_total = None
    best_index = None
    best_route = None
    for index in range(len(route) + 1):
        trial = list(route)
        trial.insert(index, node)
        total = route_cost(trial)
        if (
            best_total is None
            or total < best_total - 1e-12
            or (abs(total - best_total) <= 1e-12 and index < best_index)
        ):
            best_total = total
            best_index = index
            best_route = trial
    return best_total, best_index, best_route


def _evaluate_candidate_strict(state: ConstructionState, loc: Loc, remaining_demand: int, weights: ObjectiveWeights):
    available = state.remaining_stock.get(loc.lid, 0)
    if available <= 0 or remaining_demand <= 0:
        return None

    take = min(remaining_demand, available)
    new_floor = loc.floor not in state.active_floors
    new_thm = loc.thm_id not in state.active_thms
    new_node = loc.node2d not in state.active_nodes_by_floor[loc.floor]
    current_route = state.route_by_floor[loc.floor]
    current_cost = state.route_cost_by_floor[loc.floor]

    if new_node:
        new_total_cost, insert_index, route_nodes = _strict_best_position_cost(current_route, loc.node2d)
        route_delta = new_total_cost - current_cost
    else:
        route_delta = 0.0
        insert_index = len(current_route)
        route_nodes = None
        new_total_cost = None

    marginal_cost = (
        weights.distance * route_delta
        + (weights.thm if new_thm else 0.0)
        + (weights.floor if new_floor else 0.0)
    )
    unit_cost = marginal_cost / max(take, 1)

    return _CandidateWrapper(
        loc=loc,
        take=take,
        unit_cost=unit_cost,
        marginal_cost=marginal_cost,
        route_delta=route_delta,
        insert_index=insert_index,
        new_floor=new_floor,
        new_thm=new_thm,
        new_node=new_node,
        route_nodes=route_nodes,
        route_total_cost=new_total_cost,
        route_policy=None,
    )


def _clone_state(base_state: ConstructionState, loc_lookup: dict[str, Loc], weights: ObjectiveWeights) -> ConstructionState:
    cloned = ConstructionState(loc_lookup, weights, route_estimator="insertion")
    cloned.remaining_stock = dict(base_state.remaining_stock)
    cloned.picks_by_location = dict(base_state.picks_by_location)
    cloned.picks_by_article = defaultdict(dict, {article: dict(picks) for article, picks in base_state.picks_by_article.items()})
    cloned.active_floors = set(base_state.active_floors)
    cloned.active_thms = set(base_state.active_thms)
    cloned.active_nodes_by_floor = defaultdict(set, {floor: set(nodes) for floor, nodes in base_state.active_nodes_by_floor.items()})
    cloned.route_by_floor = defaultdict(list, {floor: list(route) for floor, route in base_state.route_by_floor.items()})
    cloned.route_cost_by_floor = defaultdict(float, {floor: float(cost) for floor, cost in base_state.route_cost_by_floor.items()})
    cloned.route_policy_by_floor = dict(base_state.route_policy_by_floor)
    return cloned


def run_phase1(
    demands: dict[int, int],
    loc_lookup: dict[str, Loc],
    article_to_candidates: dict[int, list[Loc]],
    weights: ObjectiveWeights,
    *,
    time_limit: float,
) -> tuple[ConstructionState, dict[str, object]]:
    state = ConstructionState(loc_lookup, weights, route_estimator="insertion")
    counts = {article: len(candidates) for article, candidates in article_to_candidates.items()}
    distribution = Counter(counts.values())
    articles_1 = [article for article, count in counts.items() if count == 1]
    groups = {count: [article for article, article_count in counts.items() if article_count == count] for count in sorted(distribution) if count >= 2}

    prep_start = time.perf_counter()
    for article in articles_1:
        remaining = demands[article]
        loc = article_to_candidates[article][0]
        while remaining > 0:
            candidate = state.evaluate_candidate(loc, remaining)
            state.commit(candidate)
            remaining -= candidate.take
    prep_elapsed = time.perf_counter() - prep_start

    start = time.perf_counter()
    completed = {group: 0 for group in groups}
    finish_times = {}
    remaining_groups = {group: 0 for group in groups}
    fast_reuse_steps = 0
    strict_steps = 0
    partial_group = None

    for group_size in sorted(groups):
        articles = groups[group_size]
        for index, article in enumerate(articles):
            if time.perf_counter() - start >= time_limit:
                remaining_groups[group_size] = len(articles) - index
                for later_group in sorted(groups):
                    if later_group > group_size:
                        remaining_groups[later_group] = len(groups[later_group])
                partial_group = group_size
                return state, {
                    "single_location_articles": len(articles_1),
                    "distribution": dict(sorted(distribution.items())),
                    "prep_elapsed": prep_elapsed,
                    "phase1_elapsed": time.perf_counter() - start,
                    "completed_by_exact_group": completed,
                    "group_finish_times": finish_times,
                    "remaining_if_any": {group: remaining for group, remaining in remaining_groups.items() if remaining},
                    "partial_group": partial_group,
                    "fast_reuse_steps": fast_reuse_steps,
                    "strict_steps": strict_steps,
                }

            remaining = demands[article]
            while remaining > 0:
                feasible = [loc for loc in article_to_candidates[article] if state.remaining_stock.get(loc.lid, 0) > 0]
                open_thm_locs = [loc for loc in feasible if loc.thm_id in state.active_thms]

                if open_thm_locs:
                    scored = []
                    for loc in open_thm_locs:
                        candidate = state.evaluate_candidate(loc, remaining)
                        if candidate is not None:
                            scored.append(candidate)
                    scored.sort(key=candidate_sort_key)
                    best = scored[0]
                    state.commit(best)
                    remaining -= best.take
                    fast_reuse_steps += 1
                    continue

                scored = []
                for loc in feasible:
                    candidate = _evaluate_candidate_strict(state, loc, remaining, weights)
                    if candidate is not None:
                        scored.append(candidate)
                scored.sort(key=candidate_sort_key)
                best = scored[0]
                state.commit(best)
                remaining -= best.take
                strict_steps += 1
            completed[group_size] += 1
        finish_times[group_size] = time.perf_counter() - start

    return state, {
        "single_location_articles": len(articles_1),
        "distribution": dict(sorted(distribution.items())),
        "prep_elapsed": prep_elapsed,
        "phase1_elapsed": time.perf_counter() - start,
        "completed_by_exact_group": completed,
        "group_finish_times": finish_times,
        "remaining_if_any": {},
        "partial_group": None,
        "fast_reuse_steps": fast_reuse_steps,
        "strict_steps": strict_steps,
    }


def solve(
    order_path: str | Path,
    stock_path: str | Path,
    *,
    distance_weight: float = 1.0,
    thm_weight: float = 15.0,
    floor_weight: float = 30.0,
    phase1_limit: float = 120.0,
    iterations: int = 25,
    alpha: float = 0.25,
    article_rcl_size: int = 6,
    location_rcl_size: int = 5,
    seed: int = 7,
):
    total_start = time.perf_counter()
    weights = ObjectiveWeights(distance=distance_weight, thm=thm_weight, floor=floor_weight)
    demands, relevant_locs, loc_lookup, article_to_candidates = prepare_problem(order_path, stock_path)

    phase1_state, phase1_notes = run_phase1(
        demands,
        loc_lookup,
        article_to_candidates,
        weights,
        time_limit=phase1_limit,
    )

    picked_by_article = {article: sum(picks.values()) for article, picks in phase1_state.picks_by_article.items()}
    residual_demands = {
        article: demand - picked_by_article.get(article, 0)
        for article, demand in demands.items()
        if demand - picked_by_article.get(article, 0) > 0
    }

    residual_locs: list[Loc] = []
    residual_lookup: dict[str, Loc] = {}
    residual_candidates: dict[int, list[Loc]] = defaultdict(list)
    for loc in relevant_locs:
        remaining_stock = phase1_state.remaining_stock.get(loc.lid, 0)
        if remaining_stock <= 0 or loc.article not in residual_demands:
            continue
        residual_loc = Loc(
            lid=loc.lid,
            thm_id=loc.thm_id,
            article=loc.article,
            floor=loc.floor,
            aisle=loc.aisle,
            side=loc.side,
            column=loc.column,
            shelf=loc.shelf,
            stock=remaining_stock,
        )
        residual_locs.append(residual_loc)
        residual_lookup[residual_loc.lid] = residual_loc
        residual_candidates[residual_loc.article].append(residual_loc)

    residual_candidates = dict(residual_candidates)
    base_order = compute_article_order(residual_demands, residual_candidates, weights) if residual_demands else []

    rng = random.Random(seed)
    best_solution = None
    best_state = None
    best_objective = float("inf")
    best_iteration = 0

    phase2_start = time.perf_counter()
    max_iterations = max(1, iterations) if residual_demands else 0
    for completed_iterations in range(max_iterations):
        iteration_number = completed_iterations + 1
        deterministic = iteration_number == 1
        state = _clone_state(phase1_state, loc_lookup, weights)
        remaining_articles = list(base_order)

        while remaining_articles:
            article_limit = 1 if deterministic else max(1, min(article_rcl_size, len(remaining_articles)))
            article_index = 0 if deterministic else rng.randrange(article_limit)
            article = remaining_articles.pop(article_index)

            remaining = residual_demands[article]
            while remaining > 0:
                choice = choose_randomized_candidate(
                    article,
                    remaining,
                    residual_candidates,
                    state,
                    alpha=alpha,
                    location_rcl_size=location_rcl_size,
                    rng=rng,
                    deterministic=deterministic,
                )
                state.commit(choice)
                remaining -= choice.take

        candidate_solution = build_solution(
            algorithm="2min Strict Prepass + GRASP Residual (No 2-opt)",
            picks_by_location=state.picks_by_location,
            demands=demands,
            relevant_locs=relevant_locs,
            loc_lookup=loc_lookup,
            weights=weights,
            solve_time=0.0,
            phase_times={},
            notes={},
            route_hints_by_floor=dict(state.route_by_floor),
            two_opt_passes=0,
        )
        if candidate_solution.objective_value + 1e-9 < best_objective:
            best_solution = candidate_solution
            best_state = state
            best_objective = candidate_solution.objective_value
            best_iteration = iteration_number

    phase2_elapsed = time.perf_counter() - phase2_start
    total_elapsed = time.perf_counter() - total_start

    if best_solution is None:
        best_solution = build_solution(
            algorithm="2min Strict Prepass + GRASP Residual (No 2-opt)",
            picks_by_location=phase1_state.picks_by_location,
            demands=demands,
            relevant_locs=relevant_locs,
            loc_lookup=loc_lookup,
            weights=weights,
            solve_time=0.0,
            phase_times={},
            notes={},
            route_hints_by_floor=dict(phase1_state.route_by_floor),
            two_opt_passes=0,
        )
        best_state = phase1_state

    best_solution.algorithm = "2min Strict Prepass + GRASP Residual (No 2-opt)"
    best_solution.solve_time = total_elapsed
    best_solution.phase_times = {
        "phase1_prepass": phase1_notes["phase1_elapsed"],
        "phase2_grasp_search": phase2_elapsed,
        "total": total_elapsed,
    }
    best_solution.notes.update(
        {
            "best_iteration": best_iteration,
            "iterations_run": max_iterations,
            "seed": seed,
            "rcl_alpha": f"{alpha:.2f}",
            "article_rcl_size": article_rcl_size,
            "location_rcl_size": location_rcl_size,
            "route_cleanup": "disabled (no 2-opt)",
            "phase1_limit_sec": phase1_limit,
            "phase1_partial_group": phase1_notes["partial_group"],
            "phase1_fast_reuse_steps": phase1_notes["fast_reuse_steps"],
            "phase1_strict_steps": phase1_notes["strict_steps"],
            "residual_articles": len(residual_demands),
            "residual_candidate_locations": len(residual_locs),
        }
    )

    summary = {
        "algorithm": best_solution.algorithm,
        "objective_value": best_solution.objective_value,
        "distance": best_solution.total_distance,
        "floors": best_solution.total_floors,
        "thms": best_solution.total_thms,
        "pick_rows": best_solution.total_picks,
        "visited_nodes": sum(result.visited_nodes for result in best_solution.floor_results),
        "solve_time": best_solution.solve_time,
        "phase_times": best_solution.phase_times,
        "notes": best_solution.notes,
        "phase1": phase1_notes,
        "best_state_route_hints": {floor: list(route) for floor, route in best_state.route_by_floor.items()},
    }
    return best_solution, summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hybrid benchmark: 120s strict prepass + GRASP residual (no 2-opt).")
    parser.add_argument("--orders", default="data/full/PickOrder.csv")
    parser.add_argument("--stock", default="data/full/StockData.csv")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument("--phase1-limit", type=float, default=120.0)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--alpha", type=float, default=0.25)
    parser.add_argument("--article-rcl-size", type=int, default=6)
    parser.add_argument("--location-rcl-size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", default="outputs/benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_pick.csv")
    parser.add_argument(
        "--alternative-locations-output",
        default="outputs/benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_full_alt.csv",
    )
    parser.add_argument(
        "--summary-output",
        default="outputs/benchmark_outputs/full_data_hybrid/strict120_open_thm_grasp_no2opt_summary.json",
    )
    args = parser.parse_args(argv)

    solution, summary = solve(
        args.orders,
        args.stock,
        distance_weight=args.distance_weight,
        thm_weight=args.thm_weight,
        floor_weight=args.floor_weight,
        phase1_limit=args.phase1_limit,
        iterations=args.iterations,
        alpha=args.alpha,
        article_rcl_size=args.article_rcl_size,
        location_rcl_size=args.location_rcl_size,
        seed=args.seed,
    )

    if args.output:
        write_pick_csv(solution, args.output)
    if args.alternative_locations_output:
        write_alternative_locations_csv(solution, args.alternative_locations_output)
    if args.summary_output:
        Path(args.summary_output).write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

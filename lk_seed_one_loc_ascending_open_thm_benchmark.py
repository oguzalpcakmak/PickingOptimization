"""Hybrid benchmark:
1) commit 1-location articles first,
2) rebuild that initial route with LK per floor,
3) process remaining articles by ascending candidate-count groups,
4) short-circuit to already-open THMs when possible,
5) fall back to strict insertion otherwise.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Sequence

from heuristic_common import (
    ConstructionState,
    ObjectiveWeights,
    build_solution,
    candidate_sort_key,
    optimize_route_with_lk,
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


def solve(
    order_path: str | Path,
    stock_path: str | Path,
    *,
    distance_weight: float = 1.0,
    thm_weight: float = 15.0,
    floor_weight: float = 30.0,
):
    weights = ObjectiveWeights(distance=distance_weight, thm=thm_weight, floor=floor_weight)
    total_start = time.perf_counter()

    demands, relevant_locs, loc_lookup, article_to_candidates = prepare_problem(order_path, stock_path)
    state = ConstructionState(loc_lookup, weights, route_estimator="insertion")

    counts = {article: len(candidates) for article, candidates in article_to_candidates.items()}
    distribution = Counter(counts.values())
    single_location_articles = [article for article, count in counts.items() if count == 1]
    groups = {count: [article for article, article_count in counts.items() if article_count == count] for count in sorted(distribution) if count >= 2}

    def evaluate_candidate_strict(loc, remaining_demand):
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

    prep_start = time.perf_counter()
    for article in single_location_articles:
        remaining = demands[article]
        loc = article_to_candidates[article][0]
        while remaining > 0:
            candidate = state.evaluate_candidate(loc, remaining)
            state.commit(candidate)
            remaining -= candidate.take
    prep_elapsed = time.perf_counter() - prep_start

    lk_seed_start = time.perf_counter()
    lk_seed_floor_times = {}
    for floor in sorted(state.active_nodes_by_floor):
        nodes = state.active_nodes_by_floor[floor]
        if not nodes:
            continue
        floor_start = time.perf_counter()
        route, cost = optimize_route_with_lk(
            nodes,
            initial_route=state.route_by_floor[floor],
            solution_method="lk2_improve",
            backtracking=(5, 5),
            reduction_level=4,
            reduction_cycle=4,
        )
        state.route_by_floor[floor] = route
        state.route_cost_by_floor[floor] = cost
        lk_seed_floor_times[floor] = time.perf_counter() - floor_start
    lk_seed_elapsed = time.perf_counter() - lk_seed_start

    grouped_start = time.perf_counter()
    completed = {group: 0 for group in groups}
    finish_times = {}
    fast_reuse_steps = 0
    strict_steps = 0
    strict_candidate_evals = 0
    strict_position_evals = 0

    for group_size in sorted(groups):
        for article in groups[group_size]:
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
                    strict_candidate_evals += 1
                    route = state.route_by_floor[loc.floor]
                    if loc.node2d not in state.active_nodes_by_floor[loc.floor]:
                        strict_position_evals += len(route) + 1
                    candidate = evaluate_candidate_strict(loc, remaining)
                    if candidate is not None:
                        scored.append(candidate)
                scored.sort(key=candidate_sort_key)
                best = scored[0]
                state.commit(best)
                remaining -= best.take
                strict_steps += 1
            completed[group_size] += 1
        finish_times[group_size] = time.perf_counter() - grouped_start

    grouped_elapsed = time.perf_counter() - grouped_start
    total_elapsed = time.perf_counter() - total_start

    solution = build_solution(
        algorithm="LK seed for 1-location articles + ascending grouped insertion + open THM shortcut",
        picks_by_location=state.picks_by_location,
        demands=demands,
        relevant_locs=relevant_locs,
        loc_lookup=loc_lookup,
        weights=weights,
        solve_time=total_elapsed,
        phase_times={
            "prep_single_location": prep_elapsed,
            "lk_seed_route": lk_seed_elapsed,
            "ascending_grouped_phase": grouped_elapsed,
            "total": total_elapsed,
        },
        notes={
            "grouping": "1-location prep -> LK route seed -> exact candidate-count groups ascending 2,3,4,...",
            "open_thm_shortcut": "enabled",
            "route_cleanup": "disabled (no 2-opt)",
            "lk_seed_floor_times": lk_seed_floor_times,
            "fast_reuse_steps": fast_reuse_steps,
            "strict_steps": strict_steps,
            "strict_candidate_evals": strict_candidate_evals,
            "strict_position_evals": strict_position_evals,
        },
        route_hints_by_floor=dict(state.route_by_floor),
        two_opt_passes=0,
    )

    summary = {
        "algorithm": solution.algorithm,
        "objective_value": solution.objective_value,
        "distance": solution.total_distance,
        "floors": solution.total_floors,
        "thms": solution.total_thms,
        "pick_rows": solution.total_picks,
        "visited_nodes": sum(result.visited_nodes for result in solution.floor_results),
        "solve_time": solution.solve_time,
        "phase_times": solution.phase_times,
        "notes": solution.notes,
        "distribution": dict(sorted(distribution.items())),
        "completed_by_exact_group": completed,
        "group_finish_times_sec": {group: round(value, 4) for group, value in finish_times.items()},
    }
    return solution, summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LK seed + ascending grouped insertion benchmark.")
    parser.add_argument("--orders", default="PickOrder.csv")
    parser.add_argument("--stock", default="StockData.csv")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument(
        "--output",
        default="benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_pick.csv",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_alt.csv",
    )
    parser.add_argument(
        "--summary-output",
        default="benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_summary.json",
    )
    args = parser.parse_args(argv)

    solution, summary = solve(
        args.orders,
        args.stock,
        distance_weight=args.distance_weight,
        thm_weight=args.thm_weight,
        floor_weight=args.floor_weight,
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

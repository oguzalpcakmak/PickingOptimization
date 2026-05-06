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
import random
import time
from collections import Counter
from pathlib import Path
from typing import Sequence

from heuristic_common import (
    ConstructionState,
    DataError,
    ObjectiveWeights,
    build_rcl,
    build_solution,
    candidate_sort_key,
    compute_article_order,
    optimize_route_with_lk,
    parse_article_list,
    parse_floor_list,
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


def _choose_from_rcl(rcl, rng: random.Random):
    if not rcl:
        raise DataError("Cannot choose from an empty restricted candidate list.")
    if len(rcl) == 1:
        return rcl[0]
    weights = list(range(len(rcl), 0, -1))
    return rng.choices(list(rcl), weights=weights, k=1)[0]


def _remaining_demand(demands, state: ConstructionState, article: int) -> int:
    picked = sum(state.picks_by_article.get(article, {}).values())
    return max(0, demands[article] - picked)


def _complete_with_grasp_style_fallback(
    state: ConstructionState,
    demands,
    article_to_candidates,
    weights: ObjectiveWeights,
    *,
    alpha: float,
    article_rcl_size: int,
    location_rcl_size: int,
    seed: int,
):
    """Finish a partial state with GRASP-style RCL choices.

    This is not a full multi-start restart. It keeps the partial strict-insertion
    solution and completes only the remaining demand with the same RCL decision
    logic used by the GRASP constructor.
    """

    start = time.perf_counter()
    rng = random.Random(seed)
    remaining_demands = {
        article: _remaining_demand(demands, state, article)
        for article in demands
        if _remaining_demand(demands, state, article) > 0
    }
    article_order = compute_article_order(remaining_demands, article_to_candidates, weights)
    remaining_articles = list(article_order)

    steps = 0
    candidate_evals = 0
    articles_completed = 0

    while remaining_articles:
        limit = max(1, min(article_rcl_size, len(remaining_articles)))
        article_index = rng.randrange(limit)
        article = remaining_articles.pop(article_index)

        while True:
            remaining = _remaining_demand(demands, state, article)
            if remaining <= 0:
                break

            scored = []
            for loc in article_to_candidates[article]:
                candidate_evals += 1
                candidate = state.evaluate_candidate(loc, remaining)
                if candidate is not None:
                    scored.append(candidate)
            if not scored:
                raise DataError(f"Article {article} still has demand {remaining}, but no feasible stock remains.")

            scored.sort(key=candidate_sort_key)
            rcl = build_rcl(scored, alpha=alpha, max_size=location_rcl_size)
            choice = _choose_from_rcl(rcl, rng)
            state.commit(choice)
            steps += 1

        articles_completed += 1

    return {
        "fallback_time": time.perf_counter() - start,
        "fallback_articles": articles_completed,
        "fallback_steps": steps,
        "fallback_candidate_evals": candidate_evals,
        "fallback_seed": seed,
        "fallback_alpha": alpha,
        "fallback_article_rcl_size": article_rcl_size,
        "fallback_location_rcl_size": location_rcl_size,
    }


def solve(
    order_path: str | Path,
    stock_path: str | Path,
    *,
    distance_weight: float = 1.0,
    thm_weight: float = 15.0,
    floor_weight: float = 30.0,
    time_limit: float | None = None,
    fallback_on_time_limit: bool = False,
    fallback_alpha: float = 0.25,
    fallback_article_rcl_size: int = 6,
    fallback_location_rcl_size: int = 5,
    fallback_seed: int = 7,
    floors: Sequence[str] | None = None,
    articles: Sequence[int] | None = None,
):
    weights = ObjectiveWeights(distance=distance_weight, thm=thm_weight, floor=floor_weight)
    total_start = time.perf_counter()
    deadline = None if time_limit is None or time_limit <= 0 else total_start + time_limit

    demands, relevant_locs, loc_lookup, article_to_candidates = prepare_problem(
        order_path,
        stock_path,
        floors=floors,
        articles=articles,
    )
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
    timed_out = False
    timeout_group = None
    timeout_article = None
    fallback_summary = {
        "fallback_time": 0.0,
        "fallback_articles": 0,
        "fallback_steps": 0,
        "fallback_candidate_evals": 0,
        "fallback_seed": fallback_seed,
        "fallback_alpha": fallback_alpha,
        "fallback_article_rcl_size": fallback_article_rcl_size,
        "fallback_location_rcl_size": fallback_location_rcl_size,
    }

    for group_size in sorted(groups):
        for article in groups[group_size]:
            remaining = demands[article]
            while remaining > 0:
                if deadline is not None and time.perf_counter() >= deadline:
                    timed_out = True
                    timeout_group = group_size
                    timeout_article = article
                    break

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
                if not scored:
                    raise DataError(f"Article {article} still has demand {remaining}, but no feasible stock remains.")
                scored.sort(key=candidate_sort_key)
                best = scored[0]
                state.commit(best)
                remaining -= best.take
                strict_steps += 1
            if timed_out:
                break
            completed[group_size] += 1
        finish_times[group_size] = time.perf_counter() - grouped_start
        if timed_out:
            break

    remaining_before_fallback = {
        article: _remaining_demand(demands, state, article)
        for article in demands
        if _remaining_demand(demands, state, article) > 0
    }
    if timed_out and fallback_on_time_limit:
        fallback_summary = _complete_with_grasp_style_fallback(
            state,
            demands,
            article_to_candidates,
            weights,
            alpha=fallback_alpha,
            article_rcl_size=fallback_article_rcl_size,
            location_rcl_size=fallback_location_rcl_size,
            seed=fallback_seed,
        )

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
            "time_limit_sec": time_limit,
            "timed_out": timed_out,
            "timeout_group": timeout_group,
            "timeout_article": timeout_article,
            "fallback_on_time_limit": fallback_on_time_limit,
            "fallback_used": timed_out and fallback_on_time_limit,
            "remaining_articles_before_fallback": len(remaining_before_fallback),
            "remaining_units_before_fallback": sum(remaining_before_fallback.values()),
            "fast_reuse_steps": fast_reuse_steps,
            "strict_steps": strict_steps,
            "strict_candidate_evals": strict_candidate_evals,
            "strict_position_evals": strict_position_evals,
            **fallback_summary,
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
    parser.add_argument("--orders", default="data/full/PickOrder.csv")
    parser.add_argument("--stock", default="data/full/StockData.csv")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument("--time-limit", type=float, default=0.0, help="Total runtime cap in seconds. 0 means unlimited.")
    parser.add_argument(
        "--fallback-on-time-limit",
        action="store_true",
        help="If the time cap is reached, finish remaining demand with GRASP-style RCL completion.",
    )
    parser.add_argument("--fallback-alpha", type=float, default=0.25)
    parser.add_argument("--fallback-article-rcl-size", type=int, default=6)
    parser.add_argument("--fallback-location-rcl-size", type=int, default=5)
    parser.add_argument("--fallback-seed", type=int, default=7)
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471")
    parser.add_argument(
        "--output",
        default="outputs/benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_pick.csv",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="outputs/benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_full_alt.csv",
    )
    parser.add_argument(
        "--summary-output",
        default="outputs/benchmark_outputs/full_data_lk_seed/lk_seed_one_loc_ascending_open_thm_summary.json",
    )
    args = parser.parse_args(argv)

    solution, summary = solve(
        args.orders,
        args.stock,
        distance_weight=args.distance_weight,
        thm_weight=args.thm_weight,
        floor_weight=args.floor_weight,
        time_limit=args.time_limit,
        fallback_on_time_limit=args.fallback_on_time_limit,
        fallback_alpha=args.fallback_alpha,
        fallback_article_rcl_size=args.fallback_article_rcl_size,
        fallback_location_rcl_size=args.fallback_location_rcl_size,
        fallback_seed=args.fallback_seed,
        floors=parse_floor_list(args.floors),
        articles=parse_article_list(args.articles),
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

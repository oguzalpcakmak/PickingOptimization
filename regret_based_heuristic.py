"""Deterministic route-aware regret heuristic for warehouse picking.

This variant is intentionally fast and reproducible:
  1. Order articles by a static regret-style priority
     (few choices first, then large best-vs-second-best gap).
  2. For each article, repeatedly choose the location with the lowest current
     weighted marginal cost per picked unit.
  3. Rebuild each floor route with regret insertion + 2-opt at the end.

Compared with the existing decomposition heuristic, this solver is more tightly
aligned with the exact model's depot-anchored distance objective.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Sequence

from heuristic_common import (
    CandidateScore,
    ConstructionState,
    DataError,
    ObjectiveWeights,
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


def choose_best_candidate(
    article: int,
    remaining_demand: int,
    candidates_by_article,
    state: ConstructionState,
) -> CandidateScore:
    scored = []
    for loc in candidates_by_article[article]:
        candidate = state.evaluate_candidate(loc, remaining_demand)
        if candidate is not None:
            scored.append(candidate)
    if not scored:
        raise DataError(f"Article {article} still has demand {remaining_demand}, but no feasible stock remains.")
    scored.sort(key=candidate_sort_key)
    return scored[0]


def solve(
    order_path: str | Path,
    stock_path: str | Path,
    *,
    floors: list[str] | None = None,
    articles: list[int] | None = None,
    distance_weight: float = 1.0,
    thm_weight: float = 15.0,
    floor_weight: float = 30.0,
    construction_route_estimator: str = "insertion",
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
    article_order = compute_article_order(demands, candidates_by_article, weights)
    phase_times["article_ordering"] = time.perf_counter() - step_start
    print(f"  Priority queue built for {len(article_order)} articles ({phase_times['article_ordering']:.2f}s)")

    step_start = time.perf_counter()
    state = ConstructionState(
        loc_lookup,
        weights,
        route_estimator=construction_route_estimator,
    )
    for index, article in enumerate(article_order, start=1):
        remaining = demands[article]
        while remaining > 0:
            choice = choose_best_candidate(article, remaining, candidates_by_article, state)
            state.commit(choice)
            remaining -= choice.take

        if index % 250 == 0 or index == len(article_order):
            print(
                f"  Constructed {index}/{len(article_order)} articles, "
                f"estimated objective={state.estimated_objective():.2f}"
            )
    phase_times["construction"] = time.perf_counter() - step_start

    step_start = time.perf_counter()
    solution = build_solution(
        algorithm="Route-Aware Regret Greedy",
        picks_by_location=state.picks_by_location,
        demands=demands,
        relevant_locs=relevant_locs,
        loc_lookup=loc_lookup,
        weights=weights,
        solve_time=0.0,
        phase_times=phase_times,
        notes={
            "article_order": "static regret priority",
            "allocation_rule": "lowest marginal cost per picked unit",
            "construction_route_estimator": construction_route_estimator,
        },
        route_hints_by_floor=dict(state.route_by_floor),
    )
    phase_times["route_rebuild"] = time.perf_counter() - step_start

    solve_time = time.perf_counter() - total_start
    phase_times["total"] = solve_time
    solution.solve_time = solve_time
    solution.phase_times = dict(phase_times)
    return solution


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic route-aware regret heuristic.")
    parser.add_argument("--orders", default="PickOrder.csv")
    parser.add_argument("--stock", default="StockData.csv")
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument(
        "--construction-route-estimator",
        choices=("best_of_4", "insertion"),
        default="insertion",
        help="Floor-route scorer used during construction. 'best_of_4' is experimental.",
    )
    parser.add_argument(
        "--output",
        "--pick-data-output",
        dest="pick_data_output",
        default="PickDataOutput_RegretHeuristic.csv",
        help="Pick CSV output path.",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput_RegretHeuristic.csv",
        help="Alternative locations CSV output path. Pass empty string to disable.",
    )
    args = parser.parse_args(argv)

    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  ROUTE-AWARE REGRET GREEDY HEURISTIC                             ║")
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
        construction_route_estimator=args.construction_route_estimator,
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

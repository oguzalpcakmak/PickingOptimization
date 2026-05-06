"""THM-first heuristic with S-shape aisle routing.

Phase 1:
  Find a minimum-cardinality THM subset that can cover all article demands.
  This is solved with the same exact branch-and-bound search used by the
  RR-style THM-first heuristic.

Phase 2:
  Route the selected picks with an adapted S-shape aisle policy. For this
  warehouse's three-cross-aisle layout, the router uses the shared
  multi-cross-aisle "s_shape" policy from heuristic_common.
"""

from __future__ import annotations

import argparse
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from heuristic_common import (
    DataError,
    FloorResult,
    Loc,
    ObjectiveWeights,
    Solution,
    floor_index,
    parse_article_list,
    parse_floor_list,
    prepare_problem,
    print_report,
    route_cost,
    write_alternative_locations_csv,
    write_pick_csv,
)
from thm_min_rr_heuristic import (
    allocate_within_selected_thms,
    build_article_candidates,
    group_thm_options,
    prune_redundant_thms,
    search_min_thm_cover,
    selected_locations,
)


def s_shape_route_for_floor(nodes: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], float]:
    if not nodes:
        return [], 0.0

    by_aisle: dict[int, list[int]] = defaultdict(list)
    for aisle, column in nodes:
        by_aisle[aisle].append(column)

    aisle_orders = [
        sorted(by_aisle),
        list(reversed(sorted(by_aisle))),
    ]

    best_route: list[tuple[int, int]] = []
    best_cost = float("inf")

    for aisle_order in aisle_orders:
        for start_front_to_back in (True, False):
            route: list[tuple[int, int]] = []
            forward = start_front_to_back
            for aisle in aisle_order:
                columns = sorted(set(by_aisle[aisle]))
                if not forward:
                    columns = list(reversed(columns))
                for column in columns:
                    route.append((aisle, column))
                forward = not forward

            distance = route_cost(route)
            if distance + 1e-9 < best_cost:
                best_cost = distance
                best_route = route

    if not best_route:
        raise DataError("S-shape route builder could not produce a visit order.")
    return best_route, best_cost


def build_solution_from_s_shape(
    *,
    picks_by_location: dict[str, int],
    demands: dict[int, int],
    relevant_locs: list[Loc],
    loc_lookup: dict[str, Loc],
    weights: ObjectiveWeights,
    solve_time: float,
    phase_times: dict[str, float],
    notes: dict[str, Any],
) -> Solution:
    picks_by_floor: dict[str, dict[str, int]] = defaultdict(dict)
    nodes_by_floor: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for lid, qty in picks_by_location.items():
        if qty <= 0:
            continue
        loc = loc_lookup[lid]
        picks_by_floor[loc.floor][lid] = qty
        nodes_by_floor[loc.floor].add((loc.aisle, loc.column))

    floor_results: list[FloorResult] = []
    total_distance = 0.0
    all_thms: set[str] = set()
    total_picks = 0

    for floor in sorted(picks_by_floor, key=floor_index):
        route, distance = s_shape_route_for_floor(sorted(nodes_by_floor[floor]))
        opened_thms = {loc_lookup[lid].thm_id for lid in picks_by_floor[floor]}
        total_distance += distance
        all_thms |= opened_thms
        total_picks += len(picks_by_floor[floor])
        floor_results.append(
            FloorResult(
                floor=floor,
                picks=dict(picks_by_floor[floor]),
                route=route,
                route_distance=distance,
                opened_thms=opened_thms,
                visited_nodes=len(route),
            )
        )

    objective_value = (
        weights.distance * total_distance
        + weights.thm * len(all_thms)
        + weights.floor * len(floor_results)
    )

    return Solution(
        algorithm="Min-THM + S-Shape Routing",
        floor_results=floor_results,
        total_distance=total_distance,
        total_thms=len(all_thms),
        total_floors=len(floor_results),
        total_picks=total_picks,
        solve_time=solve_time,
        phase_times=dict(phase_times),
        objective_value=objective_value,
        demands=dict(demands),
        relevant_locs=list(relevant_locs),
        loc_lookup=dict(loc_lookup),
        notes=dict(notes),
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
    thm_search_time_limit: float = 10.0,
) -> Solution:
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

    step_start = time.perf_counter()
    search_state = search_min_thm_cover(
        demands,
        thm_options,
        article_candidates,
        time_limit=thm_search_time_limit,
    )
    phase_times["thm_min_search"] = time.perf_counter() - step_start
    print(
        f"  THM search: best_count={search_state.best_count}, "
        f"nodes={search_state.nodes_explored}, "
        f"optimality={'proven' if search_state.optimality_proven else 'not proven'} "
        f"({phase_times['thm_min_search']:.2f}s)"
    )

    step_start = time.perf_counter()
    best_solution = None
    best_key = None
    raw_candidates = search_state.candidate_solutions or [search_state.best_selection]
    unique_candidates = []
    seen_signatures: set[tuple[str, ...]] = set()
    for selection in raw_candidates:
        signature = tuple(sorted(selection))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique_candidates.append(list(selection))

    unique_candidates.sort(
        key=lambda selection: (
            len({thm_options[thm_id].floor for thm_id in selection}),
            len({thm_options[thm_id].node_key for thm_id in selection}),
            tuple(
                (
                    floor_index(thm_options[thm_id].floor),
                    thm_options[thm_id].aisle,
                    thm_options[thm_id].column,
                    thm_id,
                )
                for thm_id in sorted(selection)
            ),
        )
    )

    for raw_selection in unique_candidates[:64]:
        pruned_selection = prune_redundant_thms(demands, raw_selection, thm_options)
        if len(pruned_selection) != search_state.best_count:
            continue
        picks_by_location = allocate_within_selected_thms(demands, pruned_selection, loc_lookup, thm_options)
        candidate_solution = build_solution_from_s_shape(
            picks_by_location=picks_by_location,
            demands=demands,
            relevant_locs=selected_locations(pruned_selection, loc_lookup, thm_options),
            loc_lookup=loc_lookup,
            weights=weights,
            solve_time=0.0,
            phase_times={},
            notes={},
        )
        tie_key = (
            candidate_solution.total_thms,
            candidate_solution.total_distance,
            candidate_solution.total_floors,
            candidate_solution.total_picks,
        )
        if best_key is None or tie_key < best_key:
            best_key = tie_key
            best_solution = candidate_solution
    if best_solution is None:
        raise DataError("Could not build a feasible pick allocation from the selected THMs.")
    phase_times["allocation_and_routing"] = time.perf_counter() - step_start

    solve_time = time.perf_counter() - total_start
    phase_times["total"] = solve_time
    best_solution.solve_time = solve_time
    best_solution.phase_times = dict(phase_times)
    best_solution.notes.update(
        {
            "phase_1_goal": "absolute THM-count minimization",
            "routing": "S-shape aisle routing",
            "thm_optimality": "proven" if search_state.optimality_proven else "best incumbent",
            "thm_search_nodes": search_state.nodes_explored,
            "thm_search_limit_s": f"{thm_search_time_limit:.1f}",
        }
    )
    return best_solution


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="THM-min-first heuristic with S-shape aisle routing.")
    parser.add_argument("--orders", default="data/full/PickOrder.csv")
    parser.add_argument("--stock", default="data/full/StockData.csv")
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument(
        "--thm-search-time-limit",
        type=float,
        default=10.0,
        help="Time budget in seconds for the exact THM minimization branch-and-bound.",
    )
    parser.add_argument(
        "--output",
        "--pick-data-output",
        dest="pick_data_output",
        default="PickDataOutput_THMMinSShape.csv",
        help="Pick CSV output path.",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput_THMMinSShape.csv",
        help="Alternative locations CSV output path. Pass empty string to disable.",
    )
    args = parser.parse_args(argv)

    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  THM-MIN + S-SHAPE ROUTING HEURISTIC                             ║")
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
        thm_search_time_limit=args.thm_search_time_limit,
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

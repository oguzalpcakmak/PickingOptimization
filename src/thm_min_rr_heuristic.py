"""THM-first heuristic with Ratliff-Rosenthal-style aisle dynamic programming.

Phase 1:
  Find a minimum-cardinality THM subset that can cover all article demands.
  This is solved with an exact branch-and-bound search whenever the time
  budget allows; otherwise the best incumbent is returned with a note.

Phase 2:
  Route the selected picks with an aisle dynamic program inspired by
  Ratliff & Rosenthal (1983). The classic paper covers a single-block
  rectangular warehouse. Our warehouse has an additional middle cross aisle,
  so this implementation uses the same left-to-right dynamic-programming
  principle but with three aisle endpoints per aisle: front, middle, back.
"""

from __future__ import annotations

import argparse
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from heuristic_common import (
    AISLE_PITCH,
    COLUMN_LENGTH,
    CROSS_AISLE_WIDTH,
    DataError,
    FLOOR_ORDER,
    FloorResult,
    Loc,
    ObjectiveWeights,
    Solution,
    floor_index,
    parse_article_list,
    parse_floor_list,
    prepare_problem,
    print_report,
    stair_position,
    write_alternative_locations_csv,
    write_pick_csv,
    x_coord,
)


FRONT = "F"
MIDDLE = "M"
BACK = "B"
ENDPOINTS = (FRONT, MIDDLE, BACK)

FRONT_Y = CROSS_AISLE_WIDTH
MIDDLE_Y = CROSS_AISLE_WIDTH + (10 * COLUMN_LENGTH) + CROSS_AISLE_WIDTH
BACK_Y = CROSS_AISLE_WIDTH + (10 * COLUMN_LENGTH) + CROSS_AISLE_WIDTH + (10 * COLUMN_LENGTH) + CROSS_AISLE_WIDTH
ENDPOINT_Y = {
    FRONT: FRONT_Y,
    MIDDLE: MIDDLE_Y,
    BACK: BACK_Y,
}

ELEVATOR_AISLES = {1: 8, 2: 18}
STAIRS = (
    {"id": 1, "aisle1": 5, "aisle2": 6, "cross_aisle": 1},
    {"id": 2, "aisle1": 15, "aisle2": 16, "cross_aisle": 1},
    {"id": 3, "aisle1": 24, "aisle2": 25, "cross_aisle": 1},
    {"id": 4, "aisle1": 9, "aisle2": 10, "cross_aisle": 2},
    {"id": 5, "aisle1": 19, "aisle2": 20, "cross_aisle": 2},
    {"id": 6, "aisle1": 4, "aisle2": 5, "cross_aisle": 3},
    {"id": 7, "aisle1": 14, "aisle2": 15, "cross_aisle": 3},
    {"id": 8, "aisle1": 23, "aisle2": 24, "cross_aisle": 3},
)


@dataclass(frozen=True)
class THMOption:
    thm_id: str
    floor: str
    aisle: int
    column: int
    node_key: tuple[str, int, int]
    loc_ids: tuple[str, ...]
    capacities: dict[int, int]
    total_cover: int
    article_count: int


@dataclass
class SearchState:
    best_count: int
    best_selection: list[str]
    candidate_solutions: list[list[str]]
    optimality_proven: bool
    timed_out: bool
    nodes_explored: int


def y_coord(column: int) -> float:
    if column <= 10:
        return CROSS_AISLE_WIDTH + ((column - 0.5) * COLUMN_LENGTH)
    return (
        CROSS_AISLE_WIDTH
        + (10 * COLUMN_LENGTH)
        + CROSS_AISLE_WIDTH
        + ((column - 10 - 0.5) * COLUMN_LENGTH)
    )


def nearest_elevator(aisle: int) -> int:
    return 1 if abs(aisle - ELEVATOR_AISLES[1]) <= abs(aisle - ELEVATOR_AISLES[2]) else 2


def nearest_stair_to_elevator(elevator_num: int) -> int:
    elevator_x = x_coord(ELEVATOR_AISLES[elevator_num])
    best_stair_id = 1
    best_distance = math.inf
    for stair in STAIRS:
        if stair["cross_aisle"] != 1:
            continue
        stair_x, _ = stair_position(stair["id"])
        distance = abs(stair_x - elevator_x)
        if distance < best_distance:
            best_distance = distance
            best_stair_id = stair["id"]
    return best_stair_id


def stair_to_elevator_distance(elevator_num: int) -> float:
    stair_id = nearest_stair_to_elevator(elevator_num)
    stair_x, _ = stair_position(stair_id)
    elevator_x = x_coord(ELEVATOR_AISLES[elevator_num])
    return abs(stair_x - elevator_x) + CROSS_AISLE_WIDTH


def depot_to_endpoint_cost(aisle: int, endpoint: str) -> float:
    elevator_num = nearest_elevator(aisle)
    horizontal = abs(aisle - ELEVATOR_AISLES[elevator_num]) * AISLE_PITCH
    return stair_to_elevator_distance(elevator_num) + horizontal + ENDPOINT_Y[endpoint] - FRONT_Y


def endpoint_to_depot_cost(aisle: int, endpoint: str) -> float:
    return depot_to_endpoint_cost(aisle, endpoint)


def horizontal_cross_aisle_cost(aisle_a: int, aisle_b: int) -> float:
    return abs(x_coord(aisle_a) - x_coord(aisle_b))


def group_thm_options(locs: Iterable[Loc]) -> dict[str, THMOption]:
    locs_by_thm: dict[str, list[Loc]] = defaultdict(list)
    for loc in locs:
        locs_by_thm[loc.thm_id].append(loc)

    options: dict[str, THMOption] = {}
    for thm_id, items in locs_by_thm.items():
        items.sort(key=lambda loc: (loc.floor, loc.aisle, loc.column, loc.shelf, loc.side, loc.lid))
        capacities: dict[int, int] = defaultdict(int)
        for loc in items:
            capacities[loc.article] += loc.stock

        anchor = items[0]
        options[thm_id] = THMOption(
            thm_id=thm_id,
            floor=anchor.floor,
            aisle=anchor.aisle,
            column=anchor.column,
            node_key=anchor.node_key,
            loc_ids=tuple(loc.lid for loc in items),
            capacities=dict(capacities),
            total_cover=sum(capacities.values()),
            article_count=len(capacities),
        )
    return options


def build_article_candidates(demands: dict[int, int], thm_options: dict[str, THMOption]) -> dict[int, list[str]]:
    candidates: dict[int, list[str]] = defaultdict(list)
    for thm_id, option in thm_options.items():
        for article, cap in option.capacities.items():
            if cap > 0 and article in demands:
                candidates[article].append(thm_id)
    for article in demands:
        if article not in candidates:
            raise DataError(f"Article {article} has no candidate THMs.")
    return dict(candidates)


def apply_thm(remaining: dict[int, int], option: THMOption) -> dict[int, int]:
    updated = dict(remaining)
    for article, cap in option.capacities.items():
        if article not in updated:
            continue
        new_value = max(0, updated[article] - cap)
        if new_value == 0:
            updated.pop(article, None)
        else:
            updated[article] = new_value
    return updated


def lower_bound_on_extra_thms(
    remaining: dict[int, int],
    available_thms: set[str],
    article_candidates: dict[int, list[str]],
    thm_options: dict[str, THMOption],
) -> int:
    if not remaining:
        return 0

    lower_bound = 0
    for article, demand in remaining.items():
        capacities = sorted(
            (
                thm_options[thm_id].capacities.get(article, 0)
                for thm_id in article_candidates[article]
                if thm_id in available_thms and thm_options[thm_id].capacities.get(article, 0) > 0
            ),
            reverse=True,
        )
        if sum(capacities) < demand:
            return math.inf
        covered = 0
        needed = 0
        for cap in capacities:
            covered += cap
            needed += 1
            if covered >= demand:
                break
        lower_bound = max(lower_bound, needed)
    return lower_bound


def select_branch_article(
    remaining: dict[int, int],
    available_thms: set[str],
    article_candidates: dict[int, list[str]],
    thm_options: dict[str, THMOption],
) -> int:
    ranked = []
    for article, demand in remaining.items():
        feasible = [
            thm_id
            for thm_id in article_candidates[article]
            if thm_id in available_thms and thm_options[thm_id].capacities.get(article, 0) > 0
        ]
        capacities = sorted((thm_options[thm_id].capacities[article] for thm_id in feasible), reverse=True)
        covered = 0
        needed = 0
        for cap in capacities:
            covered += cap
            needed += 1
            if covered >= demand:
                break
        ranked.append((-needed, len(feasible), demand, article))
    ranked.sort()
    return ranked[0][3]


def candidate_order_for_article(
    article: int,
    remaining: dict[int, int],
    available_thms: set[str],
    article_candidates: dict[int, list[str]],
    thm_options: dict[str, THMOption],
) -> list[str]:
    uncovered_articles = set(remaining)

    def score(thm_id: str) -> tuple[Any, ...]:
        option = thm_options[thm_id]
        direct = option.capacities.get(article, 0)
        indirect = sum(min(remaining[a], option.capacities.get(a, 0)) for a in uncovered_articles)
        return (
            -direct,
            -indirect,
            floor_index(option.floor),
            option.aisle,
            option.column,
            thm_id,
        )

    candidates = [
        thm_id
        for thm_id in article_candidates[article]
        if thm_id in available_thms and thm_options[thm_id].capacities.get(article, 0) > 0
    ]
    return sorted(candidates, key=score)


def greedy_cover(
    demands: dict[int, int],
    thm_options: dict[str, THMOption],
    article_candidates: dict[int, list[str]],
) -> list[str]:
    remaining = dict(demands)
    available = set(thm_options)
    selected: list[str] = []

    while remaining:
        best_thm = None
        best_key = None
        for thm_id in available:
            option = thm_options[thm_id]
            coverage = sum(min(qty, option.capacities.get(article, 0)) for article, qty in remaining.items())
            if coverage <= 0:
                continue
            key = (
                -coverage,
                -sum(1 for article in remaining if option.capacities.get(article, 0) > 0),
                floor_index(option.floor),
                option.aisle,
                option.column,
                thm_id,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_thm = thm_id

        if best_thm is None:
            raise DataError("Greedy THM cover could not satisfy all demands.")

        selected.append(best_thm)
        available.remove(best_thm)
        remaining = apply_thm(remaining, thm_options[best_thm])

    return selected


def store_candidate_selection(state: SearchState, selection: list[str]) -> None:
    signature = tuple(selection)
    existing = {tuple(candidate) for candidate in state.candidate_solutions}
    if signature in existing:
        return
    state.candidate_solutions.append(list(selection))
    if len(state.candidate_solutions) > 128:
        state.candidate_solutions = state.candidate_solutions[:128]


def search_min_thm_cover(
    demands: dict[int, int],
    thm_options: dict[str, THMOption],
    article_candidates: dict[int, list[str]],
    *,
    time_limit: float,
) -> SearchState:
    greedy_selection = greedy_cover(demands, thm_options, article_candidates)
    state = SearchState(
        best_count=len(greedy_selection),
        best_selection=list(greedy_selection),
        candidate_solutions=[list(greedy_selection)],
        optimality_proven=False,
        timed_out=False,
        nodes_explored=0,
    )

    start = time.perf_counter()

    def dfs(selection: list[str], remaining: dict[int, int], available: set[str]) -> None:
        if time_limit > 0 and time.perf_counter() - start >= time_limit:
            state.timed_out = True
            return

        state.nodes_explored += 1

        if not remaining:
            if len(selection) < state.best_count:
                state.best_count = len(selection)
                state.best_selection = list(selection)
                state.candidate_solutions = [list(selection)]
            elif len(selection) == state.best_count:
                store_candidate_selection(state, selection)
            return

        lower_bound = lower_bound_on_extra_thms(remaining, available, article_candidates, thm_options)
        if math.isinf(lower_bound):
            return
        if len(selection) + lower_bound > state.best_count:
            return

        article = select_branch_article(remaining, available, article_candidates, thm_options)
        for thm_id in candidate_order_for_article(article, remaining, available, article_candidates, thm_options):
            if len(selection) + 1 > state.best_count:
                break
            next_selection = [*selection, thm_id]
            next_remaining = apply_thm(remaining, thm_options[thm_id])
            next_available = set(available)
            next_available.remove(thm_id)
            dfs(next_selection, next_remaining, next_available)
            if state.timed_out:
                return

    dfs([], dict(demands), set(thm_options))
    state.optimality_proven = not state.timed_out
    return state


def can_cover_with_subset(
    demands: dict[int, int],
    selected_thms: Iterable[str],
    thm_options: dict[str, THMOption],
) -> bool:
    cover: dict[int, int] = defaultdict(int)
    for thm_id in selected_thms:
        for article, cap in thm_options[thm_id].capacities.items():
            cover[article] += cap
    return all(cover[article] >= demand for article, demand in demands.items())


def prune_redundant_thms(
    demands: dict[int, int],
    selected_thms: Iterable[str],
    thm_options: dict[str, THMOption],
) -> list[str]:
    current = list(selected_thms)
    changed = True
    while changed:
        changed = False
        for thm_id in list(current):
            trial = [item for item in current if item != thm_id]
            if can_cover_with_subset(demands, trial, thm_options):
                current = trial
                changed = True
                break
    return current


def selected_locations(
    selected_thms: Iterable[str],
    loc_lookup: dict[str, Loc],
    thm_options: dict[str, THMOption],
) -> list[Loc]:
    rows = []
    for thm_id in selected_thms:
        option = thm_options[thm_id]
        for lid in option.loc_ids:
            rows.append(loc_lookup[lid])
    return rows


def allocate_within_selected_thms(
    demands: dict[int, int],
    selected_thms: Iterable[str],
    loc_lookup: dict[str, Loc],
    thm_options: dict[str, THMOption],
) -> dict[str, int]:
    selected = set(selected_thms)
    selected_locs = [
        loc
        for thm_id in selected
        for lid in thm_options[thm_id].loc_ids
        for loc in [loc_lookup[lid]]
    ]

    by_article: dict[int, list[Loc]] = defaultdict(list)
    total_capacity: dict[int, int] = defaultdict(int)
    for loc in selected_locs:
        by_article[loc.article].append(loc)
        total_capacity[loc.article] += loc.stock

    for article, demand in demands.items():
        if total_capacity[article] < demand:
            raise DataError(f"Selected THMs cannot allocate article {article}.")

    picks: dict[str, int] = {}
    remaining = dict(demands)
    used_on_node: set[tuple[str, int, int]] = set()

    scarcity = {}
    for article, candidates in by_article.items():
        scarcity[article] = len({loc.thm_id for loc in candidates})

    for article in sorted(demands, key=lambda a: (scarcity[a], demands[a], a)):
        need = remaining[article]
        candidates = sorted(
            by_article[article],
            key=lambda loc: (
                0 if loc.node_key in used_on_node else 1,
                floor_index(loc.floor),
                loc.aisle,
                loc.column,
                loc.shelf,
                loc.thm_id,
                loc.lid,
            ),
        )
        for loc in candidates:
            if need <= 0:
                break
            take = min(need, loc.stock)
            if take <= 0:
                continue
            picks[loc.lid] = picks.get(loc.lid, 0) + take
            used_on_node.add(loc.node_key)
            need -= take
        if need > 0:
            raise DataError(f"Could not allocate article {article} inside the selected THMs.")

    return picks


def shortest_line_cover_cost(columns: Sequence[int], start_endpoint: str, end_endpoint: str) -> tuple[float, str]:
    positions = sorted(y_coord(column) for column in set(columns))
    left = positions[0]
    right = positions[-1]
    start_y = ENDPOINT_Y[start_endpoint]
    end_y = ENDPOINT_Y[end_endpoint]

    forward = abs(start_y - left) + (right - left) + abs(end_y - right)
    backward = abs(start_y - right) + (right - left) + abs(end_y - left)
    if forward <= backward:
        return forward, "LR"
    return backward, "RL"


def first_visit_column_order(columns: Sequence[int], start_endpoint: str, end_endpoint: str, pattern: str) -> list[int]:
    unique_columns = sorted(set(columns), key=y_coord)
    start_y = ENDPOINT_Y[start_endpoint]
    end_y = ENDPOINT_Y[end_endpoint]
    left_y = y_coord(unique_columns[0])
    right_y = y_coord(unique_columns[-1])

    if pattern == "LR":
        checkpoints = [start_y, left_y, right_y, end_y]
    else:
        checkpoints = [start_y, right_y, left_y, end_y]

    seen: set[int] = set()
    order: list[int] = []

    for seg_start, seg_end in zip(checkpoints, checkpoints[1:]):
        ascending = seg_end >= seg_start
        segment_columns = [
            column
            for column in unique_columns
            if min(seg_start, seg_end) - 1e-9 <= y_coord(column) <= max(seg_start, seg_end) + 1e-9
        ]
        if not ascending:
            segment_columns = list(reversed(segment_columns))
        for column in segment_columns:
            if column not in seen:
                seen.add(column)
                order.append(column)

    for column in unique_columns:
        if column not in seen:
            order.append(column)
    return order


def rr_style_route_for_floor(nodes: Sequence[tuple[int, int]]) -> tuple[list[tuple[int, int]], float]:
    if not nodes:
        return [], 0.0

    by_aisle: dict[int, list[int]] = defaultdict(list)
    for aisle, column in nodes:
        by_aisle[aisle].append(column)

    aisle_orders = [
        sorted(by_aisle),
        list(reversed(sorted(by_aisle))),
    ]

    best_nodes: list[tuple[int, int]] = []
    best_cost = math.inf

    for aisle_order in aisle_orders:
        service_costs: dict[int, dict[tuple[str, str], tuple[float, str]]] = {}
        for aisle in aisle_order:
            service_costs[aisle] = {}
            for start in ENDPOINTS:
                for end in ENDPOINTS:
                    service_costs[aisle][(start, end)] = shortest_line_cover_cost(by_aisle[aisle], start, end)

        dp: list[dict[str, tuple[float, tuple[str, str] | None]]] = []
        first_aisle = aisle_order[0]
        first_layer: dict[str, tuple[float, tuple[str, str] | None]] = {}
        for start in ENDPOINTS:
            for end in ENDPOINTS:
                cost, _ = service_costs[first_aisle][(start, end)]
                total = depot_to_endpoint_cost(first_aisle, start) + cost
                current = first_layer.get(end)
                marker = ("START", start)
                if current is None or total < current[0]:
                    first_layer[end] = (total, marker)
        dp.append(first_layer)

        for index in range(1, len(aisle_order)):
            aisle = aisle_order[index]
            prev_aisle = aisle_order[index - 1]
            layer: dict[str, tuple[float, tuple[str, str] | None]] = {}
            for entry in ENDPOINTS:
                prev_state = dp[index - 1].get(entry)
                if prev_state is None:
                    continue
                transfer = horizontal_cross_aisle_cost(prev_aisle, aisle)
                for exit_endpoint in ENDPOINTS:
                    service, _ = service_costs[aisle][(entry, exit_endpoint)]
                    total = prev_state[0] + transfer + service
                    current = layer.get(exit_endpoint)
                    marker = (entry, exit_endpoint)
                    if current is None or total < current[0]:
                        layer[exit_endpoint] = (total, marker)
            dp.append(layer)

        last_aisle = aisle_order[-1]
        best_end = None
        for end in ENDPOINTS:
            state = dp[-1].get(end)
            if state is None:
                continue
            total = state[0] + endpoint_to_depot_cost(last_aisle, end)
            if best_end is None or total < best_end[0]:
                best_end = (total, end)

        if best_end is None:
            raise DataError("RR-style route DP could not connect all aisles.")

        total_cost, end_state = best_end

        path_states: list[tuple[str, str]] = []
        current_end = end_state
        for index in range(len(aisle_order) - 1, -1, -1):
            marker = dp[index][current_end][1]
            if marker is None:
                raise DataError("Broken RR-style route predecessor chain.")
            if marker[0] == "START":
                start_endpoint = marker[1]
                path_states.append((start_endpoint, current_end))
                break
            entry, exit_endpoint = marker
            path_states.append((entry, exit_endpoint))
            current_end = entry
        path_states.reverse()

        visit_order: list[tuple[int, int]] = []
        for aisle, (start, end) in zip(aisle_order, path_states):
            _, pattern = service_costs[aisle][(start, end)]
            for column in first_visit_column_order(by_aisle[aisle], start, end, pattern):
                visit_order.append((aisle, column))

        if total_cost < best_cost:
            best_cost = total_cost
            best_nodes = visit_order

    return best_nodes, best_cost


def build_solution_from_rr(
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
        route, distance = rr_style_route_for_floor(sorted(nodes_by_floor[floor]))
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
        algorithm="Min-THM + RR-Style Aisle DP",
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
        candidate_solution = build_solution_from_rr(
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
            "routing": "Ratliff-Rosenthal-style aisle DP (3-endpoint adaptation)",
            "thm_optimality": "proven" if search_state.optimality_proven else "best incumbent",
            "thm_search_nodes": search_state.nodes_explored,
            "thm_search_limit_s": f"{thm_search_time_limit:.1f}",
        }
    )
    return best_solution


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="THM-min-first heuristic with RR-style aisle routing.")
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
        default="PickDataOutput_THMMinRR.csv",
        help="Pick CSV output path.",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput_THMMinRR.csv",
        help="Alternative locations CSV output path. Pass empty string to disable.",
    )
    args = parser.parse_args(argv)

    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  THM-MIN + RR-STYLE Aisle DP HEURISTIC                           ║")
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

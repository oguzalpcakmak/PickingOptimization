"""Shared utilities for fast warehouse-picking heuristics.

The helpers here keep the heuristic variants aligned with the exact model's
distance accounting:
  - each active floor owns one depot-anchored tour,
  - intra-floor moves use the warehouse Manhattan geometry,
  - objective = distance + opened THMs + opened floors.

The goal is to let multiple heuristic entrypoints reuse the same parsing,
scoring, routing, reporting, and CSV export code while keeping the
construction logic in separate files.
"""

from __future__ import annotations

import csv
import logging
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence


AISLE_WIDTH = 1.36
COLUMN_LENGTH = 2.90
SHELF_DEPTH = 1.16
CROSS_AISLE_WIDTH = 2.70
TOTAL_AISLES = 27
TOTAL_COLUMNS = 20
AISLE_PITCH = AISLE_WIDTH + (2 * SHELF_DEPTH)

CROSS_AISLE_1_Y = CROSS_AISLE_WIDTH / 2.0
CROSS_AISLE_2_Y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + (CROSS_AISLE_WIDTH / 2.0)
CROSS_AISLE_3_Y = (
    CROSS_AISLE_WIDTH
    + 10 * COLUMN_LENGTH
    + CROSS_AISLE_WIDTH
    + 10 * COLUMN_LENGTH
    + (CROSS_AISLE_WIDTH / 2.0)
)
CROSS_AISLE_CENTERS = (CROSS_AISLE_1_Y, CROSS_AISLE_2_Y, CROSS_AISLE_3_Y)

FLOOR_ORDER = ("MZN1", "MZN2", "MZN3", "MZN4", "MZN5", "MZN6")
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

Node2D = tuple[int, int]
NodeKey = tuple[str, int, int]

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


class DataError(ValueError):
    """Raised when the input CSVs cannot support a feasible heuristic plan."""


@dataclass(frozen=True)
class ObjectiveWeights:
    distance: float = 1.0
    thm: float = 15.0
    floor: float = 30.0


@dataclass(frozen=True)
class Loc:
    """One stock location for one article."""

    lid: str
    thm_id: str
    article: int
    floor: str
    aisle: int
    side: str
    column: int
    shelf: int
    stock: int

    @property
    def node2d(self) -> Node2D:
        return (self.aisle, self.column)

    @property
    def node_key(self) -> NodeKey:
        return (self.floor, self.aisle, self.column)


@dataclass(frozen=True)
class CandidateScore:
    loc: Loc
    take: int
    unit_cost: float
    marginal_cost: float
    route_delta: float
    insert_index: int | None
    new_floor: bool
    new_thm: bool
    new_node: bool
    route_nodes: tuple[Node2D, ...] | None = None
    route_total_cost: float | None = None
    route_policy: str | None = None


@dataclass
class FloorResult:
    floor: str
    picks: dict[str, int]
    route: list[Node2D]
    route_distance: float
    opened_thms: set[str]
    visited_nodes: int


@dataclass
class Solution:
    algorithm: str
    floor_results: list[FloorResult]
    total_distance: float
    total_thms: int
    total_floors: int
    total_picks: int
    solve_time: float
    phase_times: dict[str, float]
    objective_value: float
    demands: dict[int, int]
    relevant_locs: list[Loc]
    loc_lookup: dict[str, Loc]
    notes: dict[str, Any] = field(default_factory=dict)


class ConstructionState:
    """Incremental state used by the constructive heuristics."""

    def __init__(
        self,
        loc_lookup: dict[str, Loc],
        weights: ObjectiveWeights,
        *,
        route_estimator: str = "insertion",
    ) -> None:
        self.loc_lookup = dict(loc_lookup)
        self.weights = weights
        if route_estimator not in {"insertion", "best_of_4"}:
            raise DataError(f"Unsupported route estimator '{route_estimator}'.")
        self.route_estimator = route_estimator
        self.remaining_stock = {lid: loc.stock for lid, loc in loc_lookup.items()}
        self.picks_by_location: dict[str, int] = {}
        self.picks_by_article: dict[int, dict[str, int]] = defaultdict(dict)
        self.active_floors: set[str] = set()
        self.active_thms: set[str] = set()
        self.active_nodes_by_floor: dict[str, set[Node2D]] = defaultdict(set)
        self.route_by_floor: dict[str, list[Node2D]] = defaultdict(list)
        self.route_cost_by_floor: dict[str, float] = defaultdict(float)
        self.route_policy_by_floor: dict[str, str] = {}

    def _evaluate_route_addition(
        self,
        floor: str,
        node: Node2D,
    ) -> tuple[float, int | None, tuple[Node2D, ...] | None, float | None, str | None]:
        current_route = self.route_by_floor[floor]
        current_cost = self.route_cost_by_floor[floor]
        insertion_delta, insert_index = best_insertion(current_route, node)
        if self.route_estimator == "insertion":
            return insertion_delta, insert_index, None, None, None

        insertion_total_cost = current_cost + insertion_delta

        active_nodes = set(self.active_nodes_by_floor[floor])
        active_nodes.add(node)
        estimated_route, estimated_cost, route_policy = estimate_route_with_best_of_4(active_nodes)
        if estimated_cost + 1e-9 >= current_cost and estimated_cost + 1e-9 < insertion_total_cost:
            route_delta = estimated_cost - current_cost
            return route_delta, None, estimated_route, estimated_cost, route_policy
        return insertion_delta, insert_index, None, None, None

    def evaluate_candidate(self, loc: Loc, remaining_demand: int) -> CandidateScore | None:
        available = self.remaining_stock.get(loc.lid, 0)
        if available <= 0 or remaining_demand <= 0:
            return None

        take = min(remaining_demand, available)
        new_floor = loc.floor not in self.active_floors
        new_thm = loc.thm_id not in self.active_thms
        new_node = loc.node2d not in self.active_nodes_by_floor[loc.floor]

        if new_node:
            route_delta, insert_index, route_nodes, route_total_cost, route_policy = self._evaluate_route_addition(
                loc.floor,
                loc.node2d,
            )
        else:
            route_delta, insert_index = 0.0, len(self.route_by_floor[loc.floor])
            route_nodes, route_total_cost, route_policy = None, None, None

        marginal_cost = (
            (self.weights.distance * route_delta)
            + (self.weights.thm if new_thm else 0.0)
            + (self.weights.floor if new_floor else 0.0)
        )
        unit_cost = marginal_cost / max(take, 1)

        return CandidateScore(
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
            route_total_cost=route_total_cost,
            route_policy=route_policy,
        )

    def commit(self, candidate: CandidateScore) -> None:
        loc = candidate.loc
        qty = candidate.take
        available = self.remaining_stock.get(loc.lid, 0)
        if qty <= 0 or qty > available:
            raise DataError(
                f"Invalid commit for {loc.lid}: requested {qty}, available {available}."
            )

        self.remaining_stock[loc.lid] = available - qty
        self.picks_by_location[loc.lid] = self.picks_by_location.get(loc.lid, 0) + qty
        article_picks = self.picks_by_article[loc.article]
        article_picks[loc.lid] = article_picks.get(loc.lid, 0) + qty

        if candidate.new_floor:
            self.active_floors.add(loc.floor)
        if candidate.new_thm:
            self.active_thms.add(loc.thm_id)
        if candidate.new_node:
            floor_route = self.route_by_floor[loc.floor]
            if candidate.route_nodes is not None:
                self.route_by_floor[loc.floor] = list(candidate.route_nodes)
                self.route_cost_by_floor[loc.floor] = (
                    candidate.route_total_cost
                    if candidate.route_total_cost is not None
                    else self.route_cost_by_floor[loc.floor] + candidate.route_delta
                )
                if candidate.route_policy:
                    self.route_policy_by_floor[loc.floor] = candidate.route_policy
            else:
                if candidate.insert_index is None:
                    raise DataError(f"Missing insertion index for {loc.lid}.")
                floor_route.insert(candidate.insert_index, loc.node2d)
                self.route_cost_by_floor[loc.floor] += candidate.route_delta
            self.active_nodes_by_floor[loc.floor].add(loc.node2d)

    def estimated_objective(self) -> float:
        return (
            self.weights.distance * sum(self.route_cost_by_floor.values())
            + self.weights.thm * len(self.active_thms)
            + self.weights.floor * len(self.active_floors)
        )


def _safe_int(value: Any) -> int | None:
    try:
        text = str(value).strip()
    except Exception:
        return None
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _norm_floor(value: Any) -> str | None:
    if value is None:
        return None
    floor = str(value).strip().upper()
    return floor if floor in FLOOR_ORDER else None


def _norm_side(value: Any) -> str | None:
    if value is None:
        return None
    side = str(value).strip().upper()
    if side.startswith("L"):
        return "L"
    if side.startswith("R"):
        return "R"
    return None


def floor_index(floor: str) -> int:
    return FLOOR_ORDER.index(floor) + 1


def reversed_aisle(aisle: int) -> int:
    return TOTAL_AISLES - aisle + 1


def x_coord(aisle: int) -> float:
    return (SHELF_DEPTH + AISLE_WIDTH / 2.0) + ((reversed_aisle(aisle) - 1) * AISLE_PITCH)


def y_coord(column: int) -> float:
    if column <= 10:
        return CROSS_AISLE_WIDTH + ((column - 0.5) * COLUMN_LENGTH)
    return (
        CROSS_AISLE_WIDTH
        + (10 * COLUMN_LENGTH)
        + CROSS_AISLE_WIDTH
        + ((column - 10 - 0.5) * COLUMN_LENGTH)
    )


def same_floor_distance(node_a: Node2D, node_b: Node2D) -> float:
    aisle_a, column_a = node_a
    aisle_b, column_b = node_b
    x1, y1 = x_coord(aisle_a), y_coord(column_a)
    x2, y2 = x_coord(aisle_b), y_coord(column_b)

    if aisle_a == aisle_b:
        return abs(y1 - y2)
    return min(abs(y1 - cross_y) + abs(x1 - x2) + abs(cross_y - y2) for cross_y in CROSS_AISLE_CENTERS)


def stair_position(stair_id: int) -> tuple[float, float]:
    stair = next(stair for stair in STAIRS if stair["id"] == stair_id)
    x = (x_coord(stair["aisle1"]) + x_coord(stair["aisle2"])) / 2.0
    if stair["cross_aisle"] == 1:
        y = CROSS_AISLE_WIDTH
    elif stair["cross_aisle"] == 2:
        y = CROSS_AISLE_WIDTH + (10 * COLUMN_LENGTH)
    else:
        y = CROSS_AISLE_WIDTH + (10 * COLUMN_LENGTH) + CROSS_AISLE_WIDTH + (10 * COLUMN_LENGTH)
    return x, y


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
        horizontal_distance = abs(stair_x - elevator_x)
        if horizontal_distance < best_distance:
            best_distance = horizontal_distance
            best_stair_id = stair["id"]
    return best_stair_id


def entry_exit_distance(node: Node2D) -> float:
    aisle, column = node
    elevator_num = nearest_elevator(aisle)
    stair_id = nearest_stair_to_elevator(elevator_num)
    stair_x, _ = stair_position(stair_id)
    elevator_x = x_coord(ELEVATOR_AISLES[elevator_num])
    stair_to_elevator = abs(stair_x - elevator_x) + CROSS_AISLE_WIDTH
    elevator_to_pick = abs(aisle - ELEVATOR_AISLES[elevator_num]) * AISLE_PITCH
    elevator_to_pick += (
        CROSS_AISLE_WIDTH + ((column - 0.5) * COLUMN_LENGTH)
        if column <= 10
        else (
            CROSS_AISLE_WIDTH
            + (10 * COLUMN_LENGTH)
            + CROSS_AISLE_WIDTH
            + ((column - 10 - 0.5) * COLUMN_LENGTH)
        )
    )
    return stair_to_elevator + elevator_to_pick


def route_cost(route: Sequence[Node2D]) -> float:
    if not route:
        return 0.0
    total = entry_exit_distance(route[0])
    for index in range(len(route) - 1):
        total += same_floor_distance(route[index], route[index + 1])
    total += entry_exit_distance(route[-1])
    return total


def depot_to_endpoint_cost(aisle: int, endpoint: str) -> float:
    elevator_num = nearest_elevator(aisle)
    stair_id = nearest_stair_to_elevator(elevator_num)
    stair_x, _ = stair_position(stair_id)
    elevator_x = x_coord(ELEVATOR_AISLES[elevator_num])
    stair_to_elevator = abs(stair_x - elevator_x) + CROSS_AISLE_WIDTH
    horizontal = abs(aisle - ELEVATOR_AISLES[elevator_num]) * AISLE_PITCH
    return stair_to_elevator + horizontal + (ENDPOINT_Y[endpoint] - FRONT_Y)


def horizontal_cross_aisle_cost(aisle_a: int, aisle_b: int) -> float:
    return abs(x_coord(aisle_a) - x_coord(aisle_b))


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


def first_visit_column_order(
    columns: Sequence[int],
    start_endpoint: str,
    end_endpoint: str,
    pattern: str,
) -> list[int]:
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


def _aisle_has_upper_and_lower(columns: Sequence[int]) -> tuple[bool, bool]:
    has_upper = any(column <= 10 for column in columns)
    has_lower = any(column > 10 for column in columns)
    return has_upper, has_lower


def s_shape_allowed_pairs(columns: Sequence[int]) -> set[tuple[str, str]]:
    has_upper, has_lower = _aisle_has_upper_and_lower(columns)
    if has_upper and has_lower:
        return {(FRONT, BACK), (BACK, FRONT)}
    if has_upper:
        return {(FRONT, MIDDLE), (MIDDLE, FRONT)}
    return {(MIDDLE, BACK), (BACK, MIDDLE)}


def largest_gap_allowed_pairs(columns: Sequence[int]) -> set[tuple[str, str]]:
    has_upper, has_lower = _aisle_has_upper_and_lower(columns)
    if has_upper and has_lower:
        return {(FRONT, FRONT), (MIDDLE, MIDDLE), (BACK, BACK)}
    if has_upper:
        return {(FRONT, FRONT), (MIDDLE, MIDDLE)}
    return {(MIDDLE, MIDDLE), (BACK, BACK)}


def combined_allowed_pairs(columns: Sequence[int]) -> set[tuple[str, str]]:
    has_upper, has_lower = _aisle_has_upper_and_lower(columns)
    pairs = s_shape_allowed_pairs(columns) | largest_gap_allowed_pairs(columns)
    if has_upper and has_lower:
        pairs |= {(FRONT, MIDDLE), (MIDDLE, FRONT), (MIDDLE, BACK), (BACK, MIDDLE)}
    return pairs


def _reconstruct_dp_route(
    aisle_order: Sequence[int],
    by_aisle: dict[int, list[int]],
    allowed_pairs_by_aisle: dict[int, set[tuple[str, str]]],
) -> tuple[list[Node2D], float] | None:
    if not aisle_order:
        return [], 0.0

    service_costs: dict[int, dict[tuple[str, str], tuple[float, str]]] = {}
    for aisle in aisle_order:
        aisle_service_costs: dict[tuple[str, str], tuple[float, str]] = {}
        for start, end in allowed_pairs_by_aisle[aisle]:
            aisle_service_costs[(start, end)] = shortest_line_cover_cost(by_aisle[aisle], start, end)
        if not aisle_service_costs:
            return None
        service_costs[aisle] = aisle_service_costs

    dp: list[dict[str, tuple[float, tuple[str, str] | None]]] = []
    first_aisle = aisle_order[0]
    first_layer: dict[str, tuple[float, tuple[str, str] | None]] = {}
    for start, end in service_costs[first_aisle]:
        cost, _ = service_costs[first_aisle][(start, end)]
        total = depot_to_endpoint_cost(first_aisle, start) + cost
        current = first_layer.get(end)
        marker = ("START", start)
        if current is None or total < current[0]:
            first_layer[end] = (total, marker)
    if not first_layer:
        return None
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
            for start, end in service_costs[aisle]:
                if start != entry:
                    continue
                service, _ = service_costs[aisle][(start, end)]
                total = prev_state[0] + transfer + service
                current = layer.get(end)
                marker = (entry, end)
                if current is None or total < current[0]:
                    layer[end] = (total, marker)
        if not layer:
            return None
        dp.append(layer)

    last_aisle = aisle_order[-1]
    best_end_state: tuple[float, str] | None = None
    for end in ENDPOINTS:
        state = dp[-1].get(end)
        if state is None:
            continue
        total = state[0] + depot_to_endpoint_cost(last_aisle, end)
        if best_end_state is None or total < best_end_state[0]:
            best_end_state = (total, end)
    if best_end_state is None:
        return None

    current_end = best_end_state[1]
    path_states: list[tuple[str, str]] = []
    for index in range(len(aisle_order) - 1, -1, -1):
        marker = dp[index][current_end][1]
        if marker is None:
            return None
        if marker[0] == "START":
            path_states.append((marker[1], current_end))
            break
        entry, end = marker
        path_states.append((entry, end))
        current_end = entry
    path_states.reverse()

    route: list[Node2D] = []
    for aisle, (start, end) in zip(aisle_order, path_states):
        _, pattern = service_costs[aisle][(start, end)]
        for column in first_visit_column_order(by_aisle[aisle], start, end, pattern):
            route.append((aisle, column))
    return route, route_cost(route)


def _build_combined_break_candidates(aisles: Sequence[int]) -> list[int]:
    if len(aisles) < 3:
        return []
    return list(range(1, len(aisles) - 1))


def _median_break(aisles: Sequence[int]) -> int | None:
    candidates = _build_combined_break_candidates(aisles)
    if not candidates:
        return None
    return candidates[len(candidates) // 2]


def route_with_policy(
    nodes: Sequence[Node2D],
    *,
    policy: str,
) -> tuple[tuple[Node2D, ...], float] | None:
    if not nodes:
        return tuple(), 0.0

    by_aisle: dict[int, list[int]] = defaultdict(list)
    for aisle, column in nodes:
        by_aisle[aisle].append(column)

    sorted_aisles = sorted(by_aisle)
    aisle_orders: list[list[int]]
    if policy == "combined_plus":
        aisle_orders = [sorted_aisles, list(reversed(sorted_aisles))]
    else:
        aisle_orders = [sorted_aisles, list(reversed(sorted_aisles))]

    best_route: tuple[Node2D, ...] | None = None
    best_cost = math.inf

    for aisle_order in aisle_orders:
        allowed_sets: list[dict[int, set[tuple[str, str]]]] = []
        if policy == "s_shape":
            allowed_sets.append({aisle: s_shape_allowed_pairs(by_aisle[aisle]) for aisle in aisle_order})
        elif policy == "largest_gap":
            allowed_sets.append({aisle: largest_gap_allowed_pairs(by_aisle[aisle]) for aisle in aisle_order})
        elif policy == "combined":
            break_index = _median_break(aisle_order)
            if break_index is None:
                allowed_sets.append({aisle: combined_allowed_pairs(by_aisle[aisle]) for aisle in aisle_order})
            else:
                allowed: dict[int, set[tuple[str, str]]] = {}
                for index, aisle in enumerate(aisle_order):
                    if index < break_index:
                        allowed[aisle] = s_shape_allowed_pairs(by_aisle[aisle])
                    elif index > break_index:
                        allowed[aisle] = largest_gap_allowed_pairs(by_aisle[aisle])
                    else:
                        allowed[aisle] = combined_allowed_pairs(by_aisle[aisle])
                allowed_sets.append(allowed)
        elif policy == "combined_plus":
            break_candidates = _build_combined_break_candidates(aisle_order)
            if not break_candidates:
                allowed_sets.append({aisle: combined_allowed_pairs(by_aisle[aisle]) for aisle in aisle_order})
            else:
                for break_index in break_candidates:
                    allowed: dict[int, set[tuple[str, str]]] = {}
                    for index, aisle in enumerate(aisle_order):
                        if index < break_index:
                            allowed[aisle] = s_shape_allowed_pairs(by_aisle[aisle])
                        elif index > break_index:
                            allowed[aisle] = largest_gap_allowed_pairs(by_aisle[aisle])
                        else:
                            allowed[aisle] = combined_allowed_pairs(by_aisle[aisle])
                    allowed_sets.append(allowed)
        else:
            raise DataError(f"Unsupported route policy '{policy}'.")

        for allowed_pairs_by_aisle in allowed_sets:
            built = _reconstruct_dp_route(aisle_order, by_aisle, allowed_pairs_by_aisle)
            if built is None:
                continue
            route, cost = built
            route_key = tuple(route)
            if cost + 1e-9 < best_cost:
                best_cost = cost
                best_route = route_key

    if best_route is None:
        return None
    return best_route, best_cost


@lru_cache(maxsize=20000)
def _best_of_4_route_cached(nodes_key: tuple[Node2D, ...]) -> tuple[tuple[Node2D, ...], float, str]:
    if not nodes_key:
        return tuple(), 0.0, "empty"

    best_route: tuple[Node2D, ...] = tuple()
    best_cost = math.inf
    best_policy = "s_shape"
    for policy in ("s_shape", "largest_gap", "combined", "combined_plus"):
        built = route_with_policy(nodes_key, policy=policy)
        if built is None:
            continue
        route, cost = built
        if cost + 1e-9 < best_cost:
            best_route = route
            best_cost = cost
            best_policy = policy

    if not best_route and nodes_key:
        fallback_route, fallback_cost = optimize_route(nodes_key)
        return tuple(fallback_route), fallback_cost, "regret_insertion_fallback"
    return best_route, best_cost, best_policy


def estimate_route_with_best_of_4(nodes: Iterable[Node2D]) -> tuple[tuple[Node2D, ...], float, str]:
    nodes_key = tuple(sorted(set(nodes)))
    return _best_of_4_route_cached(nodes_key)


def insertion_options(route: Sequence[Node2D], node: Node2D) -> list[tuple[float, int]]:
    if not route:
        return [(2.0 * entry_exit_distance(node), 0)]

    options: list[tuple[float, int]] = []
    front_delta = entry_exit_distance(node) + same_floor_distance(node, route[0]) - entry_exit_distance(route[0])
    options.append((front_delta, 0))

    for index in range(len(route) - 1):
        delta = (
            same_floor_distance(route[index], node)
            + same_floor_distance(node, route[index + 1])
            - same_floor_distance(route[index], route[index + 1])
        )
        options.append((delta, index + 1))

    back_delta = same_floor_distance(route[-1], node) + entry_exit_distance(node) - entry_exit_distance(route[-1])
    options.append((back_delta, len(route)))
    options.sort(key=lambda item: (item[0], item[1]))
    return options


def best_insertion(route: Sequence[Node2D], node: Node2D) -> tuple[float, int]:
    best_delta, best_index = insertion_options(route, node)[0]
    return best_delta, best_index


def build_route(nodes: Iterable[Node2D], *, use_regret: bool = True) -> list[Node2D]:
    unique_nodes = sorted(set(nodes))
    if len(unique_nodes) <= 1:
        return unique_nodes

    seed = max(unique_nodes, key=lambda node: (entry_exit_distance(node), -node[0], -node[1]))
    route = [seed]
    remaining = set(unique_nodes)
    remaining.remove(seed)

    while remaining:
        evaluated: list[tuple[float, float, Node2D, int]] = []
        for node in remaining:
            options = insertion_options(route, node)
            best_delta, best_index = options[0]
            second_delta = options[1][0] if len(options) > 1 else best_delta
            regret = second_delta - best_delta
            evaluated.append((regret, best_delta, node, best_index))

        if use_regret:
            regret, best_delta, chosen_node, insert_index = min(
                evaluated,
                key=lambda item: (-item[0], item[1], item[2][0], item[2][1]),
            )
        else:
            regret, best_delta, chosen_node, insert_index = min(
                evaluated,
                key=lambda item: (item[1], -item[0], item[2][0], item[2][1]),
            )
        route.insert(insert_index, chosen_node)
        remaining.remove(chosen_node)

    return route


def two_opt_route(route: Sequence[Node2D], *, max_passes: int = 3) -> list[Node2D]:
    def edge_cost(left: Node2D | None, right: Node2D | None) -> float:
        if left is None and right is None:
            return 0.0
        if left is None and right is not None:
            return entry_exit_distance(right)
        if left is not None and right is None:
            return entry_exit_distance(left)
        return same_floor_distance(left, right)

    if len(route) <= 2:
        return list(route)

    best = list(route)
    pass_count = 0
    improved = True
    while improved and pass_count < max_passes:
        improved = False
        pass_count += 1
        for i in range(len(best) - 1):
            prev_node = best[i - 1] if i > 0 else None
            for j in range(i + 1, len(best)):
                next_node = best[j + 1] if j + 1 < len(best) else None
                old_cost = edge_cost(prev_node, best[i]) + edge_cost(best[j], next_node)
                new_cost = edge_cost(prev_node, best[j]) + edge_cost(best[i], next_node)
                if new_cost + 1e-9 < old_cost:
                    best[i : j + 1] = reversed(best[i : j + 1])
                    improved = True
        if not improved:
            break
    return best


def optimize_route(
    nodes: Iterable[Node2D],
    *,
    use_regret: bool = True,
    two_opt_passes: int = 3,
) -> tuple[list[Node2D], float]:
    route = build_route(nodes, use_regret=use_regret)
    route = two_opt_route(route, max_passes=two_opt_passes)
    return route, route_cost(route)


def _load_lk_runtime():
    repo_root = Path(__file__).resolve().parent
    lk_src = repo_root / "lk_heuristic-master" / "src"
    if str(lk_src) not in sys.path:
        sys.path.insert(0, str(lk_src))
    try:
        from lk_heuristic.models.node import Node  # type: ignore
        from lk_heuristic.models.tsp import Tsp  # type: ignore
    except ModuleNotFoundError as exc:
        raise DataError(
            "Lin-Kernighan runtime could not be imported. "
            "Expected either a local 'lk_heuristic-master/src' checkout or an installed "
            "'lk_heuristic' package."
        ) from exc
    return Node, Tsp


def _seed_route_from_hint(
    nodes: set[Node2D],
    hinted_route: Sequence[Node2D] | None,
) -> list[Node2D] | None:
    if not hinted_route:
        return None
    route = [node for node in hinted_route if node in nodes]
    seen = set(route)
    for node in sorted(nodes - seen):
        _, insert_index = best_insertion(route, node)
        route.insert(insert_index, node)
    return route


def optimize_route_with_lk(
    nodes: Iterable[Node2D],
    *,
    initial_route: Sequence[Node2D] | None = None,
    solution_method: str = "lk2_improve",
    backtracking: tuple[int, int] = (5, 5),
    reduction_level: int = 4,
    reduction_cycle: int = 4,
) -> tuple[list[Node2D], float]:
    unique_nodes = sorted(set(nodes))
    if len(unique_nodes) <= 1:
        return unique_nodes, route_cost(unique_nodes)

    Node, Tsp = _load_lk_runtime()

    class WarehouseLKNode(Node):
        def __init__(self, warehouse_node: Node2D | None, *, is_depot: bool = False) -> None:
            super().__init__()
            self.warehouse_node = warehouse_node
            self.is_depot = is_depot

    unique_node_set = set(unique_nodes)
    seed_route = None if initial_route is None else [node for node in initial_route if node in unique_node_set]
    if not seed_route:
        seed_route, _ = optimize_route(unique_nodes, use_regret=True, two_opt_passes=2)

    seen = set(seed_route)
    for node in unique_nodes:
        if node not in seen:
            seed_route.append(node)

    depot = WarehouseLKNode(None, is_depot=True)
    lk_nodes = [depot] + [WarehouseLKNode(node) for node in seed_route]

    def warehouse_cost(left, right) -> float:
        if left.is_depot and right.is_depot:
            return 0.0
        if left.is_depot:
            return entry_exit_distance(right.warehouse_node)
        if right.is_depot:
            return entry_exit_distance(left.warehouse_node)
        return same_floor_distance(left.warehouse_node, right.warehouse_node)

    tsp = Tsp(
        lk_nodes,
        warehouse_cost,
        shuffle=False,
        backtracking=backtracking,
        reduction_level=reduction_level,
        reduction_cycle=reduction_cycle,
        tour_type="cycle",
        logging_level=logging.WARNING,
    )
    solver = tsp.methods.get(solution_method)
    if solver is None:
        raise DataError(f"Unsupported LK solution method '{solution_method}'.")
    solver()

    ordered_nodes = tsp.tour.get_nodes(start_node=depot)
    route = [node.warehouse_node for node in ordered_nodes if not node.is_depot]
    return route, route_cost(route)


def rebuild_route(
    active_nodes: Iterable[Node2D],
    *,
    hinted_route: Sequence[Node2D] | None = None,
    route_rebuild_threshold: int | None = 60,
    use_regret: bool = True,
    two_opt_passes: int = 3,
    route_optimizer: str = "regret_2opt",
    lk_backtracking: tuple[int, int] = (5, 5),
    lk_reduction_level: int = 4,
    lk_reduction_cycle: int = 4,
) -> tuple[list[Node2D], float]:
    nodes = set(active_nodes)
    if not nodes:
        return [], 0.0

    seed_route = None
    should_rebuild_from_scratch = (
        route_rebuild_threshold is None or len(nodes) <= route_rebuild_threshold
    )
    if hinted_route and not should_rebuild_from_scratch:
        seed_route = _seed_route_from_hint(nodes, hinted_route)

    if route_optimizer == "regret_2opt":
        if seed_route is not None:
            route = two_opt_route(seed_route, max_passes=two_opt_passes)
            return route, route_cost(route)
        return optimize_route(nodes, use_regret=use_regret, two_opt_passes=two_opt_passes)

    if route_optimizer in {
        "imported_city_swap",
        "imported_simulated_annealing",
        "imported_genetic",
    }:
        from imported_tsp_route_optimizers import optimize_route_with_imported_tsp

        if seed_route is None:
            seed_route, _ = optimize_route(nodes, use_regret=use_regret, two_opt_passes=two_opt_passes)
        route = optimize_route_with_imported_tsp(
            sorted(nodes),
            initial_route=seed_route,
            optimizer=route_optimizer,
            depot_cost=entry_exit_distance,
            pair_cost=same_floor_distance,
        )
        return route, route_cost(route)

    if route_optimizer not in {"lk1_improve", "lk2_improve"}:
        raise DataError(f"Unsupported route optimizer '{route_optimizer}'.")

    return optimize_route_with_lk(
        nodes,
        initial_route=seed_route,
        solution_method=route_optimizer,
        backtracking=lk_backtracking,
        reduction_level=lk_reduction_level,
        reduction_cycle=lk_reduction_cycle,
    )


def load_demands(path: str | Path) -> dict[int, int]:
    totals: dict[int, int] = defaultdict(int)
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            article = _safe_int(row.get("ARTICLE_CODE"))
            amount = _safe_int(row.get("AMOUNT"))
            if article is None or amount is None:
                continue
            if amount < 0:
                raise DataError(f"Negative demand for article {article}.")
            totals[article] += amount
    return dict(totals)


def load_stock(path: str | Path) -> list[Loc]:
    aggregated: dict[tuple[Any, ...], int] = defaultdict(int)
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            article = _safe_int(row.get("ARTICLE_CODE"))
            aisle = _safe_int(row.get("AISLE"))
            column = _safe_int(row.get("COLUMN"))
            shelf = _safe_int(row.get("SHELF"))
            stock = _safe_int(row.get("STOCK"))
            floor = _norm_floor(row.get("FLOOR"))
            side = _norm_side(row.get("RIGHT_OR_LEFT") or row.get("LEFT_OR_RIGHT"))
            thm_id = str(row.get("THM_ID", "")).strip()

            if None in (article, aisle, column, shelf, stock) or floor is None or side is None or not thm_id:
                continue
            if stock <= 0:
                continue
            if not (1 <= aisle <= TOTAL_AISLES) or not (1 <= column <= TOTAL_COLUMNS):
                continue

            key = (thm_id, article, floor, aisle, side, column, shelf)
            aggregated[key] += stock

    locs: list[Loc] = []
    for index, (key, stock) in enumerate(sorted(aggregated.items()), start=1):
        thm_id, article, floor, aisle, side, column, shelf = key
        locs.append(
            Loc(
                lid=f"j{index:05d}",
                thm_id=thm_id,
                article=article,
                floor=floor,
                aisle=aisle,
                side=side,
                column=column,
                shelf=shelf,
                stock=stock,
            )
        )
    return locs


def parse_floor_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    tokens = [token.strip().upper() for token in value.split(",") if token.strip()]
    if not tokens:
        return None
    invalid = [token for token in tokens if token not in FLOOR_ORDER]
    if invalid:
        raise DataError(f"Invalid floor filter(s): {', '.join(invalid)}")
    return tokens


def parse_article_list(value: str | None) -> list[int] | None:
    if value is None:
        return None
    items = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            items.append(int(token))
        except ValueError as exc:
            raise DataError(f"Invalid article filter '{token}'.") from exc
    return items or None


def prepare_problem(
    order_path: str | Path,
    stock_path: str | Path,
    *,
    floors: Iterable[str] | None = None,
    articles: Iterable[int] | None = None,
) -> tuple[dict[int, int], list[Loc], dict[str, Loc], dict[int, list[Loc]]]:
    demands = load_demands(order_path)
    all_locs = load_stock(stock_path)

    floor_filter = {floor.upper() for floor in floors} if floors else None
    article_filter = {int(article) for article in articles} if articles else None

    if article_filter is not None:
        demands = {article: qty for article, qty in demands.items() if article in article_filter}

    relevant_locs = [loc for loc in all_locs if loc.article in demands]
    if floor_filter is not None:
        relevant_locs = [loc for loc in relevant_locs if loc.floor in floor_filter]

    loc_lookup = {loc.lid: loc for loc in relevant_locs}
    by_article: dict[int, list[Loc]] = defaultdict(list)
    stock_by_article: dict[int, int] = defaultdict(int)
    for loc in relevant_locs:
        by_article[loc.article].append(loc)
        stock_by_article[loc.article] += loc.stock

    missing = [article for article in demands if article not in by_article]
    if missing:
        preview = ", ".join(str(article) for article in missing[:10])
        suffix = " ..." if len(missing) > 10 else ""
        raise DataError(f"No stock rows found for demanded article(s): {preview}{suffix}")

    infeasible = [
        (article, demands[article], stock_by_article[article])
        for article in demands
        if stock_by_article[article] < demands[article]
    ]
    if infeasible:
        article, demand, stock = infeasible[0]
        raise DataError(
            f"Insufficient stock for article {article}: demand={demand}, available={stock}."
        )

    for article in by_article:
        by_article[article].sort(
            key=lambda loc: (
                floor_index(loc.floor),
                loc.aisle,
                loc.column,
                loc.shelf,
                loc.side,
                loc.thm_id,
                loc.lid,
            )
        )

    return demands, relevant_locs, loc_lookup, dict(by_article)


def compute_article_order(
    demands: dict[int, int],
    candidates_by_article: dict[int, list[Loc]],
    weights: ObjectiveWeights,
) -> list[int]:
    ranked: list[tuple[tuple[float, ...], int]] = []
    for article, demand in demands.items():
        candidates = candidates_by_article.get(article, [])
        if not candidates:
            raise DataError(f"Article {article} has demand but no candidate stock locations.")

        total_stock = sum(loc.stock for loc in candidates)
        floors = {loc.floor for loc in candidates}
        nodes = {loc.node_key for loc in candidates}
        base_scores = []
        for loc in candidates:
            take = min(demand, loc.stock)
            base_cost = (
                weights.distance * (2.0 * entry_exit_distance(loc.node2d))
                + weights.thm
                + weights.floor
            )
            unit_cost = base_cost / max(take, 1)
            base_scores.append(
                (
                    unit_cost,
                    base_cost,
                    -take,
                    floor_index(loc.floor),
                    loc.aisle,
                    loc.column,
                    loc.shelf,
                    loc.thm_id,
                    loc.lid,
                )
            )
        base_scores.sort()
        regret = math.inf if len(base_scores) == 1 else max(0.0, base_scores[1][0] - base_scores[0][0])
        regret_rank = -1e18 if not math.isfinite(regret) else -regret
        slack = total_stock - demand
        ranked.append(
            (
                (
                    len(candidates),
                    len(floors),
                    regret_rank,
                    len(nodes),
                    slack,
                    -demand,
                    float(article),
                ),
                article,
            )
        )
    ranked.sort(key=lambda item: item[0])
    return [article for _, article in ranked]


def candidate_sort_key(candidate: CandidateScore) -> tuple[Any, ...]:
    loc = candidate.loc
    return (
        candidate.unit_cost,
        candidate.marginal_cost,
        candidate.new_floor,
        candidate.new_thm,
        candidate.new_node,
        candidate.route_delta,
        -candidate.take,
        floor_index(loc.floor),
        loc.aisle,
        loc.column,
        loc.shelf,
        loc.side,
        loc.thm_id,
        loc.lid,
    )


def build_rcl(
    scored_candidates: Sequence[CandidateScore],
    *,
    alpha: float,
    max_size: int | None,
) -> list[CandidateScore]:
    if not scored_candidates:
        return []
    limit = len(scored_candidates) if max_size is None else max(1, min(max_size, len(scored_candidates)))
    prefix = list(scored_candidates[:limit])
    best = prefix[0].unit_cost
    worst = prefix[-1].unit_cost
    if math.isclose(best, worst, rel_tol=1e-12, abs_tol=1e-12):
        return prefix
    threshold = best + max(0.0, min(alpha, 1.0)) * (worst - best)
    rcl = [candidate for candidate in prefix if candidate.unit_cost <= threshold + 1e-12]
    return rcl or [prefix[0]]


def build_solution(
    *,
    algorithm: str,
    picks_by_location: dict[str, int],
    demands: dict[int, int],
    relevant_locs: list[Loc],
    loc_lookup: dict[str, Loc],
    weights: ObjectiveWeights,
    solve_time: float,
    phase_times: dict[str, float],
    notes: dict[str, Any] | None = None,
    use_regret_routing: bool = True,
    two_opt_passes: int = 3,
    route_hints_by_floor: dict[str, list[Node2D]] | None = None,
    route_rebuild_threshold: int | None = 60,
    route_optimizer: str = "regret_2opt",
    lk_backtracking: tuple[int, int] = (5, 5),
    lk_reduction_level: int = 4,
    lk_reduction_cycle: int = 4,
) -> Solution:
    picks_by_floor: dict[str, dict[str, int]] = defaultdict(dict)
    active_nodes_by_floor: dict[str, set[Node2D]] = defaultdict(set)

    for lid, qty in picks_by_location.items():
        if qty <= 0:
            continue
        loc = loc_lookup[lid]
        picks_by_floor[loc.floor][lid] = qty
        active_nodes_by_floor[loc.floor].add(loc.node2d)

    floor_results: list[FloorResult] = []
    for floor in sorted(picks_by_floor, key=floor_index):
        hinted_route = None
        if route_hints_by_floor is not None:
            hinted_route = list(route_hints_by_floor.get(floor, []))

        route, distance = rebuild_route(
            active_nodes_by_floor[floor],
            hinted_route=hinted_route,
            route_rebuild_threshold=route_rebuild_threshold,
            use_regret=use_regret_routing,
            two_opt_passes=two_opt_passes,
            route_optimizer=route_optimizer,
            lk_backtracking=lk_backtracking,
            lk_reduction_level=lk_reduction_level,
            lk_reduction_cycle=lk_reduction_cycle,
        )
        opened_thms = {loc_lookup[lid].thm_id for lid in picks_by_floor[floor]}
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

    all_thms: set[str] = set()
    total_picks = 0
    for floor_result in floor_results:
        all_thms |= floor_result.opened_thms
        total_picks += len(floor_result.picks)

    total_distance = sum(floor_result.route_distance for floor_result in floor_results)
    objective_value = (
        weights.distance * total_distance
        + weights.thm * len(all_thms)
        + weights.floor * len(floor_results)
    )

    return Solution(
        algorithm=algorithm,
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
        notes=dict(notes or {}),
    )


def _node_id_map(locs: Iterable[Loc]) -> dict[NodeKey, str]:
    keys = sorted({loc.node_key for loc in locs}, key=lambda item: (floor_index(item[0]), item[1], item[2]))
    return {key: f"n{index:05d}" for index, key in enumerate(keys, start=1)}


def write_pick_csv(solution: Solution, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for floor_result in solution.floor_results:
        route_positions = {node: index + 1 for index, node in enumerate(floor_result.route)}
        for lid, qty in floor_result.picks.items():
            loc = solution.loc_lookup[lid]
            rows.append(
                {
                    "PICKER_ID": f"PICKER_{loc.floor}",
                    "THM_ID": loc.thm_id,
                    "ARTICLE_CODE": loc.article,
                    "FLOOR": loc.floor,
                    "AISLE": loc.aisle,
                    "COLUMN": loc.column,
                    "SHELF": loc.shelf,
                    "LEFT_OR_RIGHT": loc.side,
                    "AMOUNT": qty,
                    "PICKCAR_ID": f"PICKCAR_{loc.floor}",
                    "PICK_ORDER": route_positions[loc.node2d],
                }
            )

    rows.sort(
        key=lambda row: (
            floor_index(str(row["FLOOR"])),
            int(row["PICK_ORDER"]),
            int(row["AISLE"]),
            int(row["COLUMN"]),
            int(row["SHELF"]),
            str(row["LEFT_OR_RIGHT"]),
            str(row["THM_ID"]),
            int(row["ARTICLE_CODE"]),
        )
    )

    fieldnames = [
        "PICKER_ID",
        "THM_ID",
        "ARTICLE_CODE",
        "FLOOR",
        "AISLE",
        "COLUMN",
        "SHELF",
        "LEFT_OR_RIGHT",
        "AMOUNT",
        "PICKCAR_ID",
        "PICK_ORDER",
    ]
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def write_alternative_locations_csv(solution: Solution, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    picked_qty_by_location: dict[str, int] = {}
    active_nodes: set[NodeKey] = set()
    active_thms: set[str] = set()
    route_position: dict[NodeKey, int] = {}
    node_id_map = _node_id_map(solution.relevant_locs)

    for floor_result in solution.floor_results:
        active_thms |= floor_result.opened_thms
        for index, node in enumerate(floor_result.route, start=1):
            key = (floor_result.floor, node[0], node[1])
            active_nodes.add(key)
            route_position[key] = index
        for lid, qty in floor_result.picks.items():
            picked_qty_by_location[lid] = picked_qty_by_location.get(lid, 0) + qty

    rows: list[dict[str, Any]] = []
    for loc in solution.relevant_locs:
        node_key = loc.node_key
        picked_qty = picked_qty_by_location.get(loc.lid, 0)
        rows.append(
            {
                "ARTICLE_CODE": loc.article,
                "ARTICLE_DEMAND": solution.demands[loc.article],
                "LOCATION_ID": loc.lid,
                "THM_ID": loc.thm_id,
                "FLOOR": loc.floor,
                "AISLE": loc.aisle,
                "COLUMN": loc.column,
                "SHELF": loc.shelf,
                "LEFT_OR_RIGHT": loc.side,
                "AVAILABLE_STOCK": loc.stock,
                "NODE_ID": node_id_map[node_key],
                "NODE_VISITED": 1 if node_key in active_nodes else 0,
                "THM_OPENED": 1 if loc.thm_id in active_thms else 0,
                "IS_SELECTED": 1 if picked_qty > 0 else 0,
                "PICKED_AMOUNT": picked_qty,
                "PICK_ORDER": route_position.get(node_key, ""),
            }
        )

    rows.sort(
        key=lambda row: (
            int(row["ARTICLE_CODE"]),
            -int(row["IS_SELECTED"]),
            int(row["PICK_ORDER"]) if str(row["PICK_ORDER"]).strip() else 10**9,
            floor_index(str(row["FLOOR"])),
            int(row["AISLE"]),
            int(row["COLUMN"]),
            int(row["SHELF"]),
            str(row["LEFT_OR_RIGHT"]),
            str(row["THM_ID"]),
            str(row["LOCATION_ID"]),
        )
    )

    fieldnames = [
        "ARTICLE_CODE",
        "ARTICLE_DEMAND",
        "LOCATION_ID",
        "THM_ID",
        "FLOOR",
        "AISLE",
        "COLUMN",
        "SHELF",
        "LEFT_OR_RIGHT",
        "AVAILABLE_STOCK",
        "NODE_ID",
        "NODE_VISITED",
        "THM_OPENED",
        "IS_SELECTED",
        "PICKED_AMOUNT",
        "PICK_ORDER",
    ]
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def print_report(solution: Solution) -> None:
    print()
    print("=" * 72)
    print(f"  {solution.algorithm.upper()} — RESULTS")
    print("=" * 72)
    print()
    print(f"  Objective value:            {solution.objective_value:.2f}")
    print(f"  Total distance:             {solution.total_distance:.2f} m")
    print(f"  Active floors:              {solution.total_floors}")
    print(f"  Opened THMs:                {solution.total_thms}")
    print(f"  Pick rows:                  {solution.total_picks}")
    if solution.notes:
        for key, value in solution.notes.items():
            print(f"  {key}:".ljust(29) + f"{value}")
    print()
    print("  Floor details:")
    for floor_result in solution.floor_results:
        print(
            f"    {floor_result.floor}: {len(floor_result.picks)} locations, "
            f"{len(floor_result.opened_thms)} THMs, "
            f"{floor_result.visited_nodes} nodes, "
            f"distance={floor_result.route_distance:.1f}m"
        )
    print()
    print("  Phase times:")
    for phase, elapsed in solution.phase_times.items():
        print(f"    {phase:25s}  {elapsed:.4f} s")
    print()
    print(f"  Total solve time:           {solution.solve_time:.2f} s")
    print("=" * 72)

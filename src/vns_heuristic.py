"""Variable Neighborhood Search heuristic for warehouse picking.

This solver is built for practical speed on the current codebase:
  1. start from a strong constructive seed (fast THM-first or regret greedy),
  2. improve it with fast exact re-evaluation on only the affected floors,
  3. alternate between increasingly larger shake neighborhoods.

The search focuses on move types that fit the weighted objective directly:
  - relocate one selected location to an alternative source,
  - close a lightly used THM and repair greedily,
  - close a lightly used floor and repair greedily.
"""

from __future__ import annotations

import argparse
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from fast_thm_first_s_shape_heuristic import fast_prune_redundant_thms, greedy_cover_fast
from heuristic_common import (
    CandidateScore,
    ConstructionState,
    DataError,
    Loc,
    ObjectiveWeights,
    best_insertion,
    build_solution,
    candidate_sort_key,
    compute_article_order,
    estimate_route_with_best_of_4,
    entry_exit_distance,
    floor_index,
    optimize_route,
    parse_article_list,
    parse_floor_list,
    prepare_problem,
    print_report,
    route_cost,
    same_floor_distance,
    two_opt_route,
    write_alternative_locations_csv,
    write_pick_csv,
)
from thm_min_rr_heuristic import allocate_within_selected_thms, build_article_candidates, group_thm_options

Node2D = tuple[int, int]


def choose_best_candidate(
    article: int,
    remaining_demand: int,
    candidates_by_article: dict[int, list[Loc]],
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


def rebuild_floor_route(
    active_nodes: Iterable[Node2D],
    hinted_route: Sequence[Node2D] | None,
    *,
    threshold: int = 60,
) -> tuple[list[Node2D], float]:
    nodes = set(active_nodes)
    if not nodes:
        return [], 0.0

    if hinted_route and len(nodes) > threshold:
        route = [node for node in hinted_route if node in nodes]
        seen = set(route)
        for node in sorted(nodes - seen):
            _, insert_index = best_insertion(route, node)
            route.insert(insert_index, node)
        route = two_opt_route(route, max_passes=2)
        return route, route_cost(route)

    return optimize_route(nodes, use_regret=True, two_opt_passes=2)


@dataclass
class ExactEvaluation:
    objective_value: float
    total_distance: float
    total_thms: int
    total_floors: int
    route_updates: dict[str, list[Node2D]]
    route_cost_updates: dict[str, float]
    node_count_updates: dict[str, dict[Node2D, int]]


@dataclass
class MutableAllocationState:
    loc_lookup: dict[str, Loc]
    weights: ObjectiveWeights
    picks_by_location: dict[str, int]
    selected_lids_by_article: defaultdict[int, dict[str, int]]
    selected_lids_by_thm: defaultdict[str, set[str]]
    selected_lids_by_floor: defaultdict[str, set[str]]
    node_counts_by_floor: defaultdict[str, dict[Node2D, int]]
    route_by_floor: dict[str, list[Node2D]]
    route_cost_by_floor: dict[str, float]
    total_distance: float
    total_thms: int
    total_floors: int
    objective_value: float

    @classmethod
    def from_picks(
        cls,
        picks_by_location: dict[str, int],
        loc_lookup: dict[str, Loc],
        weights: ObjectiveWeights,
        *,
        route_hints_by_floor: dict[str, list[Node2D]] | None = None,
    ) -> "MutableAllocationState":
        picks = {lid: qty for lid, qty in picks_by_location.items() if qty > 0}
        selected_lids_by_article: defaultdict[int, dict[str, int]] = defaultdict(dict)
        selected_lids_by_thm: defaultdict[str, set[str]] = defaultdict(set)
        selected_lids_by_floor: defaultdict[str, set[str]] = defaultdict(set)
        node_counts_by_floor: defaultdict[str, dict[Node2D, int]] = defaultdict(dict)

        for lid, qty in picks.items():
            loc = loc_lookup[lid]
            selected_lids_by_article[loc.article][lid] = qty
            selected_lids_by_thm[loc.thm_id].add(lid)
            selected_lids_by_floor[loc.floor].add(lid)
            floor_nodes = node_counts_by_floor[loc.floor]
            floor_nodes[loc.node2d] = floor_nodes.get(loc.node2d, 0) + 1

        route_by_floor: dict[str, list[Node2D]] = {}
        route_cost_by_floor: dict[str, float] = {}
        total_distance = 0.0
        for floor in sorted(node_counts_by_floor, key=floor_index):
            hinted_route = None if route_hints_by_floor is None else route_hints_by_floor.get(floor)
            route, cost = rebuild_floor_route(set(node_counts_by_floor[floor]), hinted_route)
            route_by_floor[floor] = route
            route_cost_by_floor[floor] = cost
            total_distance += cost

        total_thms = len(selected_lids_by_thm)
        total_floors = len(selected_lids_by_floor)
        objective_value = (
            weights.distance * total_distance
            + weights.thm * total_thms
            + weights.floor * total_floors
        )
        return cls(
            loc_lookup=dict(loc_lookup),
            weights=weights,
            picks_by_location=picks,
            selected_lids_by_article=selected_lids_by_article,
            selected_lids_by_thm=selected_lids_by_thm,
            selected_lids_by_floor=selected_lids_by_floor,
            node_counts_by_floor=node_counts_by_floor,
            route_by_floor=route_by_floor,
            route_cost_by_floor=route_cost_by_floor,
            total_distance=total_distance,
            total_thms=total_thms,
            total_floors=total_floors,
            objective_value=objective_value,
        )

    def clone(self) -> "MutableAllocationState":
        return MutableAllocationState(
            loc_lookup=self.loc_lookup,
            weights=self.weights,
            picks_by_location=dict(self.picks_by_location),
            selected_lids_by_article=defaultdict(
                dict,
                {article: dict(lids) for article, lids in self.selected_lids_by_article.items()},
            ),
            selected_lids_by_thm=defaultdict(
                set,
                {thm_id: set(lids) for thm_id, lids in self.selected_lids_by_thm.items()},
            ),
            selected_lids_by_floor=defaultdict(
                set,
                {floor: set(lids) for floor, lids in self.selected_lids_by_floor.items()},
            ),
            node_counts_by_floor=defaultdict(
                dict,
                {floor: dict(counts) for floor, counts in self.node_counts_by_floor.items()},
            ),
            route_by_floor={floor: list(route) for floor, route in self.route_by_floor.items()},
            route_cost_by_floor=dict(self.route_cost_by_floor),
            total_distance=self.total_distance,
            total_thms=self.total_thms,
            total_floors=self.total_floors,
            objective_value=self.objective_value,
        )

    def available_capacity(self, lid: str, extra_added: int = 0) -> int:
        loc = self.loc_lookup[lid]
        return loc.stock - self.picks_by_location.get(lid, 0) - extra_added

    def evaluate_changes_exact(self, changes: dict[str, int]) -> ExactEvaluation | None:
        nonzero_changes = {lid: delta for lid, delta in changes.items() if delta}
        if not nonzero_changes:
            return None

        article_balance: dict[int, int] = defaultdict(int)
        affected_floors: set[str] = set()
        toggles: list[tuple[Loc, bool, bool]] = []

        for lid, delta in nonzero_changes.items():
            loc = self.loc_lookup[lid]
            current_qty = self.picks_by_location.get(lid, 0)
            new_qty = current_qty + delta
            if new_qty < 0 or new_qty > loc.stock:
                return None
            article_balance[loc.article] += delta
            was_selected = current_qty > 0
            will_be_selected = new_qty > 0
            if was_selected != will_be_selected:
                toggles.append((loc, was_selected, will_be_selected))
                affected_floors.add(loc.floor)

        if any(balance != 0 for balance in article_balance.values()):
            return None

        thm_counts_before: dict[str, int] = {}
        thm_counts_after: dict[str, int] = {}
        floor_counts_before: dict[str, int] = {}
        floor_counts_after: dict[str, int] = {}
        for loc, _, _ in toggles:
            thm_id = loc.thm_id
            floor = loc.floor
            if thm_id not in thm_counts_before:
                thm_counts_before[thm_id] = len(self.selected_lids_by_thm.get(thm_id, set()))
                thm_counts_after[thm_id] = thm_counts_before[thm_id]
            if floor not in floor_counts_before:
                floor_counts_before[floor] = len(self.selected_lids_by_floor.get(floor, set()))
                floor_counts_after[floor] = floor_counts_before[floor]

        for loc, was_selected, will_be_selected in toggles:
            if was_selected and not will_be_selected:
                thm_counts_after[loc.thm_id] -= 1
                floor_counts_after[loc.floor] -= 1
            elif not was_selected and will_be_selected:
                thm_counts_after[loc.thm_id] += 1
                floor_counts_after[loc.floor] += 1

        total_thms = self.total_thms
        for thm_id, before in thm_counts_before.items():
            after = thm_counts_after[thm_id]
            if before == 0 and after > 0:
                total_thms += 1
            elif before > 0 and after == 0:
                total_thms -= 1

        total_floors = self.total_floors
        for floor, before in floor_counts_before.items():
            after = floor_counts_after[floor]
            if before == 0 and after > 0:
                total_floors += 1
            elif before > 0 and after == 0:
                total_floors -= 1

        total_distance = self.total_distance
        route_updates: dict[str, list[Node2D]] = {}
        route_cost_updates: dict[str, float] = {}
        node_count_updates: dict[str, dict[Node2D, int]] = {}

        if affected_floors:
            toggles_by_floor: dict[str, list[tuple[Loc, bool, bool]]] = defaultdict(list)
            for loc, was_selected, will_be_selected in toggles:
                toggles_by_floor[loc.floor].append((loc, was_selected, will_be_selected))

            for floor in affected_floors:
                counts = dict(self.node_counts_by_floor.get(floor, {}))
                for loc, was_selected, will_be_selected in toggles_by_floor[floor]:
                    if was_selected and not will_be_selected:
                        updated_count = counts.get(loc.node2d, 0) - 1
                        if updated_count <= 0:
                            counts.pop(loc.node2d, None)
                        else:
                            counts[loc.node2d] = updated_count
                    elif not was_selected and will_be_selected:
                        counts[loc.node2d] = counts.get(loc.node2d, 0) + 1

                route, cost = rebuild_floor_route(set(counts), self.route_by_floor.get(floor))
                total_distance += cost - self.route_cost_by_floor.get(floor, 0.0)
                route_updates[floor] = route
                route_cost_updates[floor] = cost
                node_count_updates[floor] = counts

        objective_value = (
            self.weights.distance * total_distance
            + self.weights.thm * total_thms
            + self.weights.floor * total_floors
        )
        return ExactEvaluation(
            objective_value=objective_value,
            total_distance=total_distance,
            total_thms=total_thms,
            total_floors=total_floors,
            route_updates=route_updates,
            route_cost_updates=route_cost_updates,
            node_count_updates=node_count_updates,
        )

    def apply_changes(self, changes: dict[str, int], evaluation: ExactEvaluation) -> None:
        for lid, delta in changes.items():
            if not delta:
                continue
            loc = self.loc_lookup[lid]
            current_qty = self.picks_by_location.get(lid, 0)
            new_qty = current_qty + delta

            if new_qty <= 0:
                self.picks_by_location.pop(lid, None)
                self.selected_lids_by_article[loc.article].pop(lid, None)
                if not self.selected_lids_by_article[loc.article]:
                    self.selected_lids_by_article.pop(loc.article, None)
                thm_lids = self.selected_lids_by_thm.get(loc.thm_id)
                if thm_lids is not None:
                    thm_lids.discard(lid)
                    if not thm_lids:
                        self.selected_lids_by_thm.pop(loc.thm_id, None)
                floor_lids = self.selected_lids_by_floor.get(loc.floor)
                if floor_lids is not None:
                    floor_lids.discard(lid)
                    if not floor_lids:
                        self.selected_lids_by_floor.pop(loc.floor, None)
            else:
                self.picks_by_location[lid] = new_qty
                self.selected_lids_by_article[loc.article][lid] = new_qty
                self.selected_lids_by_thm[loc.thm_id].add(lid)
                self.selected_lids_by_floor[loc.floor].add(lid)

        for floor, counts in evaluation.node_count_updates.items():
            if counts:
                self.node_counts_by_floor[floor] = dict(counts)
            else:
                self.node_counts_by_floor.pop(floor, None)

        for floor, route in evaluation.route_updates.items():
            if route:
                self.route_by_floor[floor] = list(route)
                self.route_cost_by_floor[floor] = evaluation.route_cost_updates[floor]
            else:
                self.route_by_floor.pop(floor, None)
                self.route_cost_by_floor.pop(floor, None)

        self.total_distance = evaluation.total_distance
        self.total_thms = evaluation.total_thms
        self.total_floors = evaluation.total_floors
        self.objective_value = evaluation.objective_value


def build_route_hints_from_picks(
    picks_by_location: dict[str, int],
    loc_lookup: dict[str, Loc],
) -> dict[str, list[Node2D]]:
    nodes_by_floor: dict[str, set[Node2D]] = defaultdict(set)
    for lid, qty in picks_by_location.items():
        if qty <= 0:
            continue
        loc = loc_lookup[lid]
        nodes_by_floor[loc.floor].add(loc.node2d)

    hints: dict[str, list[Node2D]] = {}
    for floor, nodes in nodes_by_floor.items():
        route, _, _ = estimate_route_with_best_of_4(nodes)
        hints[floor] = list(route)
    return hints


def build_fast_thm_seed(
    demands: dict[int, int],
    relevant_locs: list[Loc],
    loc_lookup: dict[str, Loc],
    *,
    rng: random.Random,
    candidate_pool_size: int,
) -> tuple[dict[str, int], dict[str, list[Node2D]]]:
    thm_options = group_thm_options(relevant_locs)
    article_candidates = build_article_candidates(demands, thm_options)
    selection = greedy_cover_fast(
        demands,
        thm_options,
        article_candidates,
        rng=rng,
        deterministic=True,
        candidate_pool_size=candidate_pool_size,
    )
    selection = fast_prune_redundant_thms(demands, selection, thm_options)
    picks = allocate_within_selected_thms(demands, selection, loc_lookup, thm_options)
    return picks, build_route_hints_from_picks(picks, loc_lookup)


def build_regret_seed(
    demands: dict[int, int],
    loc_lookup: dict[str, Loc],
    candidates_by_article: dict[int, list[Loc]],
    weights: ObjectiveWeights,
) -> tuple[dict[str, int], dict[str, list[Node2D]]]:
    article_order = compute_article_order(demands, candidates_by_article, weights)
    state = ConstructionState(loc_lookup, weights, route_estimator="insertion")
    for article in article_order:
        remaining = demands[article]
        while remaining > 0:
            choice = choose_best_candidate(article, remaining, candidates_by_article, state)
            state.commit(choice)
            remaining -= choice.take
    return dict(state.picks_by_location), {floor: list(route) for floor, route in state.route_by_floor.items()}


def source_priority_key(state: MutableAllocationState, lid: str) -> tuple[Any, ...]:
    loc = state.loc_lookup[lid]
    closure_bonus = 0.0
    if len(state.selected_lids_by_thm.get(loc.thm_id, set())) == 1:
        closure_bonus += state.weights.thm
    if len(state.selected_lids_by_floor.get(loc.floor, set())) == 1:
        closure_bonus += state.weights.floor
    return (
        -closure_bonus,
        -entry_exit_distance(loc.node2d),
        -state.picks_by_location[lid],
        floor_index(loc.floor),
        loc.aisle,
        loc.column,
        lid,
    )


def move_proxy_key(
    state: MutableAllocationState,
    source: Loc,
    target: Loc,
    qty: int,
    *,
    extra_added: int = 0,
) -> tuple[Any, ...]:
    source_thm_count = len(state.selected_lids_by_thm.get(source.thm_id, set()))
    source_floor_count = len(state.selected_lids_by_floor.get(source.floor, set()))
    target_thm_open = target.thm_id in state.selected_lids_by_thm
    target_floor_open = target.floor in state.selected_lids_by_floor
    source_closes_thm = source_thm_count == 1 and target.thm_id != source.thm_id
    source_closes_floor = source_floor_count == 1 and target.floor != source.floor

    thm_delta = (0 if target_thm_open or target.thm_id == source.thm_id else 1) - (1 if source_closes_thm else 0)
    floor_delta = (0 if target_floor_open or target.floor == source.floor else 1) - (1 if source_closes_floor else 0)

    target_node_active = target.node2d in state.node_counts_by_floor.get(target.floor, {})
    route_proxy = (
        0.0
        if target.floor == source.floor and target.node2d == source.node2d
        else same_floor_distance(source.node2d, target.node2d)
        if target.floor == source.floor
        else entry_exit_distance(target.node2d)
    )
    spare = state.available_capacity(target.lid, extra_added=extra_added)
    return (
        thm_delta,
        floor_delta,
        0 if target_node_active else 1,
        0 if target.floor == source.floor else 1,
        0 if target.thm_id == source.thm_id else 1,
        route_proxy,
        -spare,
        floor_index(target.floor),
        target.aisle,
        target.column,
        target.lid,
    )


def shortlist_full_transfer_targets(
    state: MutableAllocationState,
    source_lid: str,
    candidates_by_article: dict[int, list[Loc]],
    *,
    limit: int,
    blocked_thms: set[str] | None = None,
    blocked_floors: set[str] | None = None,
) -> list[Loc]:
    source = state.loc_lookup[source_lid]
    qty = state.picks_by_location[source_lid]
    ranked: list[Loc] = []
    for target in candidates_by_article[source.article]:
        if target.lid == source_lid:
            continue
        if blocked_thms and target.thm_id in blocked_thms:
            continue
        if blocked_floors and target.floor in blocked_floors:
            continue
        if state.available_capacity(target.lid) < qty:
            continue
        ranked.append(target)

    ranked.sort(key=lambda target: move_proxy_key(state, source, target, qty))
    return ranked[: max(1, limit)]


def shortlist_split_targets(
    state: MutableAllocationState,
    source_lid: str,
    candidates_by_article: dict[int, list[Loc]],
    *,
    pending_additions: dict[str, int],
    limit: int,
    blocked_thms: set[str] | None = None,
    blocked_floors: set[str] | None = None,
) -> list[Loc]:
    source = state.loc_lookup[source_lid]
    qty = state.picks_by_location[source_lid]
    ranked: list[Loc] = []
    for target in candidates_by_article[source.article]:
        if target.lid == source_lid:
            continue
        if blocked_thms and target.thm_id in blocked_thms:
            continue
        if blocked_floors and target.floor in blocked_floors:
            continue
        extra_added = pending_additions.get(target.lid, 0)
        if state.available_capacity(target.lid, extra_added=extra_added) <= 0:
            continue
        ranked.append(target)

    ranked.sort(
        key=lambda target: move_proxy_key(
            state,
            source,
            target,
            qty,
            extra_added=pending_additions.get(target.lid, 0),
        )
    )
    return ranked[: max(1, limit)]


def build_reassignment_changes(
    state: MutableAllocationState,
    source_lids: Sequence[str],
    candidates_by_article: dict[int, list[Loc]],
    *,
    target_limit: int,
    deadline: float | None = None,
    blocked_thms: set[str] | None = None,
    blocked_floors: set[str] | None = None,
) -> dict[str, int] | None:
    pending_additions: dict[str, int] = defaultdict(int)
    changes: dict[str, int] = defaultdict(int)

    def source_key(lid: str) -> tuple[Any, ...]:
        loc = state.loc_lookup[lid]
        allowed_targets = 0
        for target in candidates_by_article[loc.article]:
            if target.lid == lid:
                continue
            if blocked_thms and target.thm_id in blocked_thms:
                continue
            if blocked_floors and target.floor in blocked_floors:
                continue
            if state.available_capacity(target.lid) > 0:
                allowed_targets += 1
        return (
            allowed_targets,
            -state.picks_by_location[lid],
            floor_index(loc.floor),
            loc.aisle,
            loc.column,
            lid,
        )

    for source_lid in sorted(source_lids, key=source_key):
        if deadline is not None and time.perf_counter() >= deadline:
            return None
        remaining = state.picks_by_location[source_lid]
        if remaining <= 0:
            continue

        changes[source_lid] = changes.get(source_lid, 0) - remaining
        for target in shortlist_split_targets(
            state,
            source_lid,
            candidates_by_article,
            pending_additions=pending_additions,
            limit=target_limit,
            blocked_thms=blocked_thms,
            blocked_floors=blocked_floors,
        ):
            if deadline is not None and time.perf_counter() >= deadline:
                return None
            spare = state.available_capacity(target.lid, extra_added=pending_additions.get(target.lid, 0))
            if spare <= 0:
                continue
            take = min(remaining, spare)
            changes[target.lid] = changes.get(target.lid, 0) + take
            pending_additions[target.lid] += take
            remaining -= take
            if remaining == 0:
                break

        if remaining > 0:
            return None

    return dict(changes)


def try_improving_single_relocation(
    state: MutableAllocationState,
    candidates_by_article: dict[int, list[Loc]],
    *,
    deadline: float | None,
    rng: random.Random,
    source_sample_size: int,
    target_sample_size: int,
) -> tuple[bool, str]:
    source_lids = sorted(state.picks_by_location, key=lambda lid: source_priority_key(state, lid))
    if not source_lids:
        return False, ""

    head = source_lids[: max(1, source_sample_size // 2)]
    tail_pool = source_lids[len(head) :]
    sampled_tail = (
        rng.sample(tail_pool, k=min(max(0, source_sample_size - len(head)), len(tail_pool)))
        if tail_pool
        else []
    )
    sampled_sources = head + sampled_tail

    for source_lid in sampled_sources:
        if deadline is not None and time.perf_counter() >= deadline:
            return False, ""
        qty = state.picks_by_location[source_lid]
        for target in shortlist_full_transfer_targets(
            state,
            source_lid,
            candidates_by_article,
            limit=target_sample_size,
        ):
            if deadline is not None and time.perf_counter() >= deadline:
                return False, ""
            evaluation = state.evaluate_changes_exact({source_lid: -qty, target.lid: qty})
            if evaluation is None:
                continue
            if evaluation.objective_value + 1e-9 < state.objective_value:
                state.apply_changes({source_lid: -qty, target.lid: qty}, evaluation)
                return True, "single_relocation"

    return False, ""


def try_improving_thm_close(
    state: MutableAllocationState,
    candidates_by_article: dict[int, list[Loc]],
    *,
    deadline: float | None,
    thm_sample_size: int,
    target_sample_size: int,
    max_locations_per_neighborhood: int,
) -> tuple[bool, str]:
    candidate_thms = sorted(
        (
            (
                len(lids),
                sum(state.picks_by_location[lid] for lid in lids),
                floor_index(state.loc_lookup[next(iter(lids))].floor),
                thm_id,
            )
            for thm_id, lids in state.selected_lids_by_thm.items()
            if 0 < len(lids) <= max_locations_per_neighborhood
        )
    )

    for _, _, _, thm_id in candidate_thms[: max(1, thm_sample_size)]:
        if deadline is not None and time.perf_counter() >= deadline:
            return False, ""
        source_lids = sorted(state.selected_lids_by_thm[thm_id])
        changes = build_reassignment_changes(
            state,
            source_lids,
            candidates_by_article,
            target_limit=max(2, target_sample_size * 2),
            deadline=deadline,
            blocked_thms={thm_id},
        )
        if changes is None:
            continue
        evaluation = state.evaluate_changes_exact(changes)
        if evaluation is None:
            continue
        if evaluation.objective_value + 1e-9 < state.objective_value:
            state.apply_changes(changes, evaluation)
            return True, "thm_close"

    return False, ""


def try_improving_floor_close(
    state: MutableAllocationState,
    candidates_by_article: dict[int, list[Loc]],
    *,
    deadline: float | None,
    floor_sample_size: int,
    target_sample_size: int,
    max_locations_per_neighborhood: int,
) -> tuple[bool, str]:
    candidate_floors = sorted(
        (
            (
                len(lids),
                sum(state.picks_by_location[lid] for lid in lids),
                floor_index(floor),
                floor,
            )
            for floor, lids in state.selected_lids_by_floor.items()
            if 0 < len(lids) <= max_locations_per_neighborhood
        )
    )

    for _, _, _, floor in candidate_floors[: max(1, floor_sample_size)]:
        if deadline is not None and time.perf_counter() >= deadline:
            return False, ""
        source_lids = sorted(state.selected_lids_by_floor[floor])
        changes = build_reassignment_changes(
            state,
            source_lids,
            candidates_by_article,
            target_limit=max(2, target_sample_size * 2),
            deadline=deadline,
            blocked_floors={floor},
        )
        if changes is None:
            continue
        evaluation = state.evaluate_changes_exact(changes)
        if evaluation is None:
            continue
        if evaluation.objective_value + 1e-9 < state.objective_value:
            state.apply_changes(changes, evaluation)
            return True, "floor_close"

    return False, ""


def shake_state(
    state: MutableAllocationState,
    candidates_by_article: dict[int, list[Loc]],
    *,
    k: int,
    rng: random.Random,
    target_sample_size: int,
) -> MutableAllocationState | None:
    shaken = state.clone()
    applied = 0
    attempts = 0
    max_attempts = max(20, 12 * k)

    while applied < k and attempts < max_attempts:
        attempts += 1
        if not shaken.picks_by_location:
            break
        source_lid = rng.choice(list(shaken.picks_by_location))
        qty = shaken.picks_by_location[source_lid]
        targets = shortlist_full_transfer_targets(
            shaken,
            source_lid,
            candidates_by_article,
            limit=max(2, target_sample_size * 2),
        )
        if not targets:
            continue
        pool = targets[: max(1, min(len(targets), target_sample_size))]
        target = rng.choice(pool)
        evaluation = shaken.evaluate_changes_exact({source_lid: -qty, target.lid: qty})
        if evaluation is None:
            continue
        shaken.apply_changes({source_lid: -qty, target.lid: qty}, evaluation)
        applied += 1

    return shaken if applied > 0 else None


def local_descent(
    state: MutableAllocationState,
    candidates_by_article: dict[int, list[Loc]],
    *,
    rng: random.Random,
    deadline: float | None,
    source_sample_size: int,
    target_sample_size: int,
    thm_sample_size: int,
    floor_sample_size: int,
    max_locations_per_neighborhood: int,
    local_step_limit: int,
    accepted_counts: dict[str, int],
) -> int:
    accepted = 0
    while accepted < local_step_limit:
        if deadline is not None and time.perf_counter() >= deadline:
            break

        improved, move_type = try_improving_floor_close(
            state,
            candidates_by_article,
            deadline=deadline,
            floor_sample_size=floor_sample_size,
            target_sample_size=target_sample_size,
            max_locations_per_neighborhood=max_locations_per_neighborhood,
        )
        if not improved:
            improved, move_type = try_improving_thm_close(
                state,
                candidates_by_article,
                deadline=deadline,
                thm_sample_size=thm_sample_size,
                target_sample_size=target_sample_size,
                max_locations_per_neighborhood=max_locations_per_neighborhood,
            )
        if not improved:
            improved, move_type = try_improving_single_relocation(
                state,
                candidates_by_article,
                deadline=deadline,
                rng=rng,
                source_sample_size=source_sample_size,
                target_sample_size=target_sample_size,
            )

        if not improved:
            break

        accepted += 1
        accepted_counts[move_type] = accepted_counts.get(move_type, 0) + 1

    return accepted


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
    max_neighborhood: int = 4,
    source_sample_size: int = 48,
    target_sample_size: int = 6,
    thm_sample_size: int = 12,
    floor_sample_size: int = 4,
    max_locations_per_neighborhood: int = 10,
    local_step_limit: int = 24,
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

    seed_choices: list[tuple[str, MutableAllocationState]] = []
    step_start = time.perf_counter()
    if seed_mode in {"fast_thm", "best"}:
        fast_picks, fast_route_hints = build_fast_thm_seed(
            demands,
            relevant_locs,
            loc_lookup,
            rng=random.Random(seed),
            candidate_pool_size=candidate_pool_size,
        )
        seed_choices.append(
            (
                "fast_thm",
                MutableAllocationState.from_picks(
                    fast_picks,
                    loc_lookup,
                    weights,
                    route_hints_by_floor=fast_route_hints,
                ),
            )
        )
    if seed_mode in {"regret", "best"}:
        regret_picks, regret_route_hints = build_regret_seed(
            demands,
            loc_lookup,
            candidates_by_article,
            weights,
        )
        seed_choices.append(
            (
                "regret",
                MutableAllocationState.from_picks(
                    regret_picks,
                    loc_lookup,
                    weights,
                    route_hints_by_floor=regret_route_hints,
                ),
            )
        )
    phase_times["seed_construction"] = time.perf_counter() - step_start

    if not seed_choices:
        raise DataError(f"Unsupported seed mode '{seed_mode}'.")

    initial_seed_name, current_state = min(seed_choices, key=lambda item: item[1].objective_value)
    initial_seed_objective = current_state.objective_value
    best_state = current_state.clone()
    print(
        f"  Initial seed: {initial_seed_name}, objective={best_state.objective_value:.2f} "
        f"({phase_times['seed_construction']:.2f}s)"
    )

    accepted_counts: dict[str, int] = {}
    search_start = time.perf_counter()
    deadline = None if time_limit <= 0 else search_start + time_limit

    initial_local_steps = local_descent(
        best_state,
        candidates_by_article,
        rng=rng,
        deadline=deadline,
        source_sample_size=source_sample_size,
        target_sample_size=target_sample_size,
        thm_sample_size=thm_sample_size,
        floor_sample_size=floor_sample_size,
        max_locations_per_neighborhood=max_locations_per_neighborhood,
        local_step_limit=local_step_limit,
        accepted_counts=accepted_counts,
    )
    if best_state.objective_value + 1e-9 < current_state.objective_value:
        print(
            f"  Seed local descent: {current_state.objective_value:.2f} -> "
            f"{best_state.objective_value:.2f} in {initial_local_steps} accepted moves"
        )
    current_state = best_state.clone()

    vns_iterations = 0
    k = 1
    while k <= max(1, max_neighborhood):
        if deadline is not None and time.perf_counter() >= deadline:
            break

        shaken = shake_state(
            current_state,
            candidates_by_article,
            k=k,
            rng=rng,
            target_sample_size=target_sample_size,
        )
        if shaken is None:
            k += 1
            continue

        local_descent(
            shaken,
            candidates_by_article,
            rng=rng,
            deadline=deadline,
            source_sample_size=source_sample_size,
            target_sample_size=target_sample_size,
            thm_sample_size=thm_sample_size,
            floor_sample_size=floor_sample_size,
            max_locations_per_neighborhood=max_locations_per_neighborhood,
            local_step_limit=local_step_limit,
            accepted_counts=accepted_counts,
        )
        vns_iterations += 1

        if shaken.objective_value + 1e-9 < best_state.objective_value:
            print(
                f"  VNS improvement at neighborhood {k}: "
                f"{best_state.objective_value:.2f} -> {shaken.objective_value:.2f}"
            )
            best_state = shaken.clone()
            current_state = shaken
            k = 1
        else:
            k += 1

    phase_times["vns_search"] = time.perf_counter() - search_start

    step_start = time.perf_counter()
    solution = build_solution(
        algorithm="Variable Neighborhood Search Heuristic",
        picks_by_location=best_state.picks_by_location,
        demands=demands,
        relevant_locs=relevant_locs,
        loc_lookup=loc_lookup,
        weights=weights,
        solve_time=0.0,
        phase_times={},
        notes={
            "seed_mode": seed_mode,
            "selected_seed": initial_seed_name,
            "initial_seed_objective": f"{initial_seed_objective:.2f}",
            "post_seed_local_objective": f"{best_state.objective_value:.2f}",
            "max_neighborhood": max_neighborhood,
            "vns_iterations": vns_iterations,
            "accepted_floor_closes": accepted_counts.get("floor_close", 0),
            "accepted_thm_closes": accepted_counts.get("thm_close", 0),
            "accepted_relocations": accepted_counts.get("single_relocation", 0),
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
    parser = argparse.ArgumentParser(description="Variable Neighborhood Search heuristic for warehouse picking.")
    parser.add_argument("--orders", default="data/full/PickOrder.csv")
    parser.add_argument("--stock", default="data/full/StockData.csv")
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument(
        "--seed-mode",
        choices=("fast_thm", "regret", "best"),
        default="fast_thm",
        help="Initial constructive solution used before the VNS improvement loop.",
    )
    parser.add_argument("--time-limit", type=float, default=20.0, help="Search time budget in seconds. Use 0 for no cap.")
    parser.add_argument("--max-neighborhood", type=int, default=4, help="Largest shake size in the VNS loop.")
    parser.add_argument("--source-sample-size", type=int, default=48, help="How many selected locations to inspect per relocation pass.")
    parser.add_argument("--target-sample-size", type=int, default=6, help="How many alternative locations to test per move.")
    parser.add_argument("--thm-sample-size", type=int, default=12, help="How many open THMs to test for closure per pass.")
    parser.add_argument("--floor-sample-size", type=int, default=4, help="How many active floors to test for closure per pass.")
    parser.add_argument("--max-locations-per-neighborhood", type=int, default=10, help="Skip THM/floor closures larger than this many picked locations.")
    parser.add_argument("--local-step-limit", type=int, default=24, help="Maximum accepted improving moves in one local-descent phase.")
    parser.add_argument("--candidate-pool-size", type=int, default=6, help="Candidate pool used by the fast THM seed.")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--output",
        "--pick-data-output",
        dest="pick_data_output",
        default="PickDataOutput_VNS.csv",
        help="Pick CSV output path.",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput_VNS.csv",
        help="Alternative locations CSV output path. Pass empty string to disable.",
    )
    args = parser.parse_args(argv)

    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  VARIABLE NEIGHBORHOOD SEARCH HEURISTIC                          ║")
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
        max_neighborhood=args.max_neighborhood,
        source_sample_size=args.source_sample_size,
        target_sample_size=args.target_sample_size,
        thm_sample_size=args.thm_sample_size,
        floor_sample_size=args.floor_sample_size,
        max_locations_per_neighborhood=args.max_locations_per_neighborhood,
        local_step_limit=args.local_step_limit,
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

"""Shared destroy/repair helpers for LNS- and ALNS-style warehouse heuristics."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

from heuristic_common import DataError, Loc, ObjectiveWeights, floor_index
from vns_heuristic import (
    MutableAllocationState,
    build_fast_thm_seed,
    build_reassignment_changes,
    build_regret_seed,
    local_descent,
    source_priority_key,
)


@dataclass(frozen=True)
class DestroyMove:
    name: str
    source_lids: tuple[str, ...]
    blocked_thms: tuple[str, ...] = ()
    blocked_floors: tuple[str, ...] = ()


def build_seed_state(
    *,
    seed_mode: str,
    demands: dict[int, int],
    relevant_locs: list[Loc],
    loc_lookup: dict[str, Loc],
    candidates_by_article: dict[int, list[Loc]],
    weights: ObjectiveWeights,
    seed: int,
    candidate_pool_size: int,
) -> tuple[str, MutableAllocationState]:
    choices: list[tuple[str, MutableAllocationState]] = []
    if seed_mode in {"fast_thm", "best"}:
        fast_picks, fast_route_hints = build_fast_thm_seed(
            demands,
            relevant_locs,
            loc_lookup,
            rng=random.Random(seed),
            candidate_pool_size=candidate_pool_size,
        )
        choices.append(
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
        choices.append(
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
    if not choices:
        raise DataError(f"Unsupported seed mode '{seed_mode}'.")
    return min(choices, key=lambda item: item[1].objective_value)


def _trim_source_lids(
    state: MutableAllocationState,
    lids: list[str],
    *,
    max_locations: int,
) -> list[str]:
    unique_lids = list(dict.fromkeys(lids))
    if len(unique_lids) <= max_locations:
        return unique_lids
    return sorted(unique_lids, key=lambda lid: source_priority_key(state, lid))[:max_locations]


def destroy_random_locations(
    state: MutableAllocationState,
    *,
    rng: random.Random,
    destroy_size: int,
    max_locations: int,
) -> DestroyMove | None:
    all_lids = list(state.picks_by_location)
    if not all_lids:
        return None
    ranked = sorted(all_lids, key=lambda lid: source_priority_key(state, lid))
    pool_size = min(len(ranked), max(destroy_size * 4, destroy_size))
    pool = ranked[:pool_size]
    sample_size = min(len(pool), max(1, min(destroy_size, max_locations)))
    chosen = rng.sample(pool, k=sample_size) if len(pool) > sample_size else pool
    chosen = _trim_source_lids(state, chosen, max_locations=max_locations)
    if not chosen:
        return None
    return DestroyMove(name="random_locations", source_lids=tuple(sorted(chosen)))


def destroy_light_thm_cluster(
    state: MutableAllocationState,
    *,
    rng: random.Random,
    destroy_size: int,
    max_locations: int,
) -> DestroyMove | None:
    if not state.selected_lids_by_thm:
        return None
    ranked = sorted(
        (
            (
                len(lids),
                sum(state.picks_by_location[lid] for lid in lids),
                floor_index(state.loc_lookup[next(iter(lids))].floor),
                state.loc_lookup[next(iter(lids))].aisle,
                thm_id,
            )
            for thm_id, lids in state.selected_lids_by_thm.items()
            if lids
        )
    )
    if not ranked:
        return None
    pool = ranked[: min(len(ranked), max(4, destroy_size * 3))]
    _, _, _, _, anchor_thm = rng.choice(pool)
    anchor_loc = state.loc_lookup[next(iter(state.selected_lids_by_thm[anchor_thm]))]
    same_floor = [
        thm_id
        for _, _, _, _, thm_id in ranked
        if state.loc_lookup[next(iter(state.selected_lids_by_thm[thm_id]))].floor == anchor_loc.floor
    ]
    same_floor.sort(
        key=lambda thm_id: (
            abs(state.loc_lookup[next(iter(state.selected_lids_by_thm[thm_id]))].aisle - anchor_loc.aisle),
            len(state.selected_lids_by_thm[thm_id]),
            thm_id,
        )
    )

    chosen_thms: list[str] = []
    chosen_lids: list[str] = []
    for thm_id in same_floor:
        candidate_lids = list(state.selected_lids_by_thm[thm_id])
        if len(chosen_thms) >= max(1, destroy_size):
            break
        if len(chosen_lids) + len(candidate_lids) > max_locations:
            continue
        chosen_thms.append(thm_id)
        chosen_lids.extend(candidate_lids)

    if not chosen_lids:
        return None
    return DestroyMove(
        name="light_thm_cluster",
        source_lids=tuple(sorted(chosen_lids)),
        blocked_thms=tuple(sorted(chosen_thms)),
    )


def destroy_route_cluster(
    state: MutableAllocationState,
    *,
    rng: random.Random,
    destroy_size: int,
    max_locations: int,
) -> DestroyMove | None:
    active_floors = [floor for floor, route in state.route_by_floor.items() if route]
    if not active_floors:
        return None
    floor_weights = [max(state.route_cost_by_floor.get(floor, 0.0), 1.0) for floor in active_floors]
    floor = rng.choices(active_floors, weights=floor_weights, k=1)[0]
    route = list(state.route_by_floor[floor])
    if not route:
        return None

    segment_len = min(len(route), max(2, destroy_size))
    if len(route) <= segment_len:
        segment = route
    else:
        start = rng.randrange(0, len(route) - segment_len + 1)
        segment = route[start : start + segment_len]
    nodes = set(segment)
    lids = [
        lid
        for lid in state.selected_lids_by_floor.get(floor, set())
        if state.loc_lookup[lid].node2d in nodes
    ]
    lids = _trim_source_lids(state, lids, max_locations=max_locations)
    if not lids:
        return None
    return DestroyMove(name="route_cluster", source_lids=tuple(sorted(lids)))


def destroy_floor_slice(
    state: MutableAllocationState,
    *,
    rng: random.Random,
    destroy_size: int,
    max_locations: int,
) -> DestroyMove | None:
    active_floors = [floor for floor, lids in state.selected_lids_by_floor.items() if lids]
    if not active_floors:
        return None
    floor = rng.choice(active_floors)
    aisles = sorted({state.loc_lookup[lid].aisle for lid in state.selected_lids_by_floor[floor]})
    if not aisles:
        return None

    window = min(len(aisles), max(1, destroy_size))
    if len(aisles) <= window:
        chosen_aisles = set(aisles)
    else:
        start = rng.randrange(0, len(aisles) - window + 1)
        chosen_aisles = set(aisles[start : start + window])

    lids = [
        lid
        for lid in state.selected_lids_by_floor[floor]
        if state.loc_lookup[lid].aisle in chosen_aisles
    ]
    lids = _trim_source_lids(state, lids, max_locations=max_locations)
    if not lids:
        return None
    return DestroyMove(name="floor_slice", source_lids=tuple(sorted(lids)))


def repair_destroyed_subset(
    state: MutableAllocationState,
    move: DestroyMove,
    candidates_by_article: dict[int, list[Loc]],
    *,
    deadline: float | None,
    target_limit: int,
    intensify_steps: int,
    rng: random.Random,
    source_sample_size: int,
    target_sample_size: int,
    thm_sample_size: int,
    floor_sample_size: int,
    max_locations_per_neighborhood: int,
) -> MutableAllocationState | None:
    changes = build_reassignment_changes(
        state,
        move.source_lids,
        candidates_by_article,
        target_limit=target_limit,
        deadline=deadline,
        blocked_thms=set(move.blocked_thms) or None,
        blocked_floors=set(move.blocked_floors) or None,
    )
    if changes is None:
        return None

    evaluation = state.evaluate_changes_exact(changes)
    if evaluation is None:
        return None

    candidate = state.clone()
    candidate.apply_changes(changes, evaluation)

    if intensify_steps > 0 and (deadline is None or time.perf_counter() < deadline):
        accepted_counts: dict[str, int] = {}
        local_descent(
            candidate,
            candidates_by_article,
            rng=rng,
            deadline=deadline,
            source_sample_size=source_sample_size,
            target_sample_size=target_sample_size,
            thm_sample_size=thm_sample_size,
            floor_sample_size=floor_sample_size,
            max_locations_per_neighborhood=max_locations_per_neighborhood,
            local_step_limit=intensify_steps,
            accepted_counts=accepted_counts,
        )

    return candidate

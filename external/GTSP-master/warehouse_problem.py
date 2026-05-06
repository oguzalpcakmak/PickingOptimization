from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Any, Iterable, Sequence

from Algorithms.Algorithms import GTSPProblem
from heuristic_common import (
    CandidateScore,
    ConstructionState,
    DataError,
    Loc,
    Node2D,
    ObjectiveWeights,
    Solution,
    build_solution,
    candidate_sort_key,
    compute_article_order,
    entry_exit_distance,
    floor_index,
    prepare_problem,
    same_floor_distance,
)


def _candidate_rank(loc: Loc, demand: int, weights: ObjectiveWeights) -> tuple[float, ...]:
    serviced_units = max(1, min(loc.stock, demand))
    base_cost = (
        weights.distance * (2.0 * entry_exit_distance(loc.node2d))
        + weights.thm
        + weights.floor
    )
    return (
        base_cost / serviced_units,
        floor_index(loc.floor),
        loc.aisle,
        loc.column,
        loc.shelf,
        0 if loc.side == "L" else 1,
        loc.thm_id,
        loc.lid,
    )


@dataclass(frozen=True)
class WarehousePoint:
    point_id: int
    cluster_index: int
    loc: Loc


class WarehouseGTSPAdapter:
    def __init__(
        self,
        order_path: str,
        stock_path: str,
        *,
        floors: Iterable[str] | None = None,
        articles: Iterable[int] | None = None,
        weights: ObjectiveWeights | None = None,
        max_candidates_per_article: int | None = 8,
        search_objective_mode: str = "construction",
        search_route_estimator: str = "insertion",
    ) -> None:
        self.weights = weights or ObjectiveWeights()
        self.max_candidates_per_article = max_candidates_per_article
        self.search_objective_mode = search_objective_mode
        self.search_route_estimator = search_route_estimator

        demands, relevant_locs, loc_lookup, candidates_by_article = prepare_problem(
            order_path,
            stock_path,
            floors=floors,
            articles=articles,
        )
        self.demands = demands
        self.relevant_locs = relevant_locs
        self.loc_lookup = loc_lookup
        self.candidates_by_article = candidates_by_article

        article_order = compute_article_order(demands, candidates_by_article, self.weights)
        self.article_by_cluster = tuple(article_order)
        self.capped_candidates_by_article: dict[int, list[Loc]] = {}

        points: list[WarehousePoint] = []
        point_to_cluster: list[int] = []
        cluster_candidates: list[tuple[int, ...]] = []
        capped_candidate_count = 0

        for cluster_index, article in enumerate(self.article_by_cluster):
            ranked_candidates = sorted(
                candidates_by_article[article],
                key=lambda loc: _candidate_rank(loc, demands[article], self.weights),
            )
            if self.max_candidates_per_article is not None and self.max_candidates_per_article > 0:
                ranked_candidates = ranked_candidates[: self.max_candidates_per_article]
            self.capped_candidates_by_article[article] = list(ranked_candidates)

            candidate_ids: list[int] = []
            for loc in ranked_candidates:
                point_id = len(points)
                points.append(WarehousePoint(point_id=point_id, cluster_index=cluster_index, loc=loc))
                point_to_cluster.append(cluster_index)
                candidate_ids.append(point_id)

            capped_candidate_count += len(candidate_ids)
            cluster_candidates.append(tuple(candidate_ids))

        self.points = tuple(points)
        self.point_to_cluster = tuple(point_to_cluster)
        self.point_id_by_lid = {point.loc.lid: point.point_id for point in self.points}
        self.problem = GTSPProblem(
            cluster_candidates=tuple(cluster_candidates),
            point_to_cluster=self.point_to_cluster,
            distance_fn=self.transition_cost,
            entry_cost_fn=self.entry_cost,
            objective_fn=self.search_objective,
            name="warehouse-gtsp",
            metadata={
                "articles": len(self.article_by_cluster),
                "points": len(self.points),
                "candidate_cap": self.max_candidates_per_article if self.max_candidates_per_article is not None else "all",
                "full_locations": len(self.relevant_locs),
                "capped_locations": capped_candidate_count,
            },
        )

    def loc_for_point(self, point_id: int) -> Loc:
        return self.points[int(point_id)].loc

    @lru_cache(maxsize=None)
    def entry_cost(self, point_id: int) -> float:
        return entry_exit_distance(self.loc_for_point(point_id).node2d)

    @lru_cache(maxsize=None)
    def transition_cost(self, left: int, right: int) -> float:
        left_loc = self.loc_for_point(left)
        right_loc = self.loc_for_point(right)
        if left_loc.floor == right_loc.floor:
            return same_floor_distance(left_loc.node2d, right_loc.node2d)
        return entry_exit_distance(left_loc.node2d) + entry_exit_distance(right_loc.node2d)

    def primary_objective(self, path: Sequence[int]) -> float:
        if len(path) != len(self.article_by_cluster):
            return math.inf
        if not path:
            return 0.0

        normalized_path = [int(point) for point in path]
        travel = self.entry_cost(normalized_path[0])
        for left, right in zip(normalized_path, normalized_path[1:]):
            travel += self.transition_cost(left, right)
        travel += self.entry_cost(normalized_path[-1])

        active_floors = {self.loc_for_point(point).floor for point in normalized_path}
        active_thms = {self.loc_for_point(point).thm_id for point in normalized_path}
        return (
            self.weights.distance * travel
            + self.weights.thm * len(active_thms)
            + self.weights.floor * len(active_floors)
        )

    def search_objective(self, path: Sequence[int]) -> float:
        if self.search_objective_mode == "primary":
            return self.primary_objective(path)
        return self.construction_objective(path)

    @lru_cache(maxsize=256)
    def _construction_objective_cached(self, path_key: tuple[int, ...]) -> float:
        if len(path_key) != len(self.article_by_cluster):
            return math.inf

        seen_articles: set[int] = set()
        state = ConstructionState(
            self.loc_lookup,
            self.weights,
            route_estimator=self.search_route_estimator,
        )
        for point_id in path_key:
            loc = self.loc_for_point(int(point_id))
            article = loc.article
            if article in seen_articles:
                return math.inf
            seen_articles.add(article)

            remaining_demand = self.demands[article]
            preferred_candidate = state.evaluate_candidate(loc, remaining_demand)
            if preferred_candidate is None:
                return math.inf
            state.commit(preferred_candidate)
            remaining_demand -= preferred_candidate.take

            while remaining_demand > 0:
                candidate = self._best_supplemental_candidate(article, state, remaining_demand)
                if candidate is None:
                    return math.inf
                state.commit(candidate)
                remaining_demand -= candidate.take

        if len(seen_articles) != len(self.article_by_cluster):
            return math.inf
        return state.estimated_objective()

    def construction_objective(self, path: Sequence[int]) -> float:
        path_key = tuple(int(point) for point in path)
        return float(self._construction_objective_cached(path_key))

    def _best_supplemental_candidate(
        self,
        article: int,
        state: ConstructionState,
        remaining_demand: int,
        candidate_pool: Sequence[Loc] | None = None,
    ) -> CandidateScore | None:
        scored: list[CandidateScore] = []
        pool = self.candidates_by_article[article] if candidate_pool is None else candidate_pool
        for loc in pool:
            candidate = state.evaluate_candidate(loc, remaining_demand)
            if candidate is None:
                continue
            scored.append(candidate)
        if not scored:
            return None
        scored.sort(key=candidate_sort_key)
        return scored[0]

    def build_seed_paths(self) -> list[list[int]]:
        state = ConstructionState(
            self.loc_lookup,
            self.weights,
            route_estimator=self.search_route_estimator,
        )
        primary_by_article: dict[int, Loc] = {}
        article_index = {article: index for index, article in enumerate(self.article_by_cluster)}

        for article in self.article_by_cluster:
            remaining_demand = self.demands[article]
            first_choice = self._best_supplemental_candidate(
                article,
                state,
                remaining_demand,
                candidate_pool=self.capped_candidates_by_article[article],
            )
            if first_choice is None:
                raise DataError(f"No capped GTSP candidate available for article {article}.")
            primary_by_article[article] = first_choice.loc
            state.commit(first_choice)
            remaining_demand -= first_choice.take

            while remaining_demand > 0:
                candidate = self._best_supplemental_candidate(article, state, remaining_demand)
                if candidate is None:
                    raise DataError(f"Unable to build GTSP seed for article {article}.")
                state.commit(candidate)
                remaining_demand -= candidate.take

        construction_path = [
            self.point_id_by_lid[primary_by_article[article].lid]
            for article in self.article_by_cluster
        ]

        route_position_by_floor: dict[str, dict[Node2D, int]] = {}
        for floor, route in state.route_by_floor.items():
            route_position_by_floor[floor] = {node: index for index, node in enumerate(route)}

        route_order_articles = sorted(
            self.article_by_cluster,
            key=lambda article: (
                floor_index(primary_by_article[article].floor),
                route_position_by_floor.get(primary_by_article[article].floor, {}).get(
                    primary_by_article[article].node2d,
                    10**9,
                ),
                primary_by_article[article].aisle,
                primary_by_article[article].column,
                article_index[article],
            ),
        )
        route_order_path = [
            self.point_id_by_lid[primary_by_article[article].lid]
            for article in route_order_articles
        ]

        reverse_route_path = list(reversed(route_order_path))
        return [construction_path, route_order_path, reverse_route_path]

    def _preferred_route_hints(self, path: Sequence[int]) -> dict[str, list[Node2D]]:
        route_hints: dict[str, list[Node2D]] = defaultdict(list)
        seen_by_floor: dict[str, set[Node2D]] = defaultdict(set)
        for point_id in path:
            loc = self.loc_for_point(int(point_id))
            if loc.node2d in seen_by_floor[loc.floor]:
                continue
            seen_by_floor[loc.floor].add(loc.node2d)
            route_hints[loc.floor].append(loc.node2d)
        return dict(route_hints)

    def build_solution_from_path(
        self,
        path: Sequence[int],
        *,
        algorithm: str,
        solve_time: float,
        phase_times: dict[str, float],
        route_estimator: str = "insertion",
        route_rebuild_threshold: int | None = 60,
        notes: dict[str, Any] | None = None,
    ) -> Solution:
        if not self.problem.is_valid_path(path):
            raise DataError("GTSP path is invalid for the current warehouse instance.")

        state = ConstructionState(self.loc_lookup, self.weights, route_estimator=route_estimator)
        route_hints_by_floor = self._preferred_route_hints(path)

        ordered_articles: list[int] = []
        preferred_by_article: dict[int, Loc] = {}
        for point_id in path:
            loc = self.loc_for_point(int(point_id))
            if loc.article in preferred_by_article:
                continue
            ordered_articles.append(loc.article)
            preferred_by_article[loc.article] = loc

        for article in ordered_articles:
            remaining_demand = self.demands[article]
            preferred_loc = preferred_by_article[article]

            preferred_candidate = state.evaluate_candidate(preferred_loc, remaining_demand)
            if preferred_candidate is not None:
                state.commit(preferred_candidate)
                remaining_demand -= preferred_candidate.take

            while remaining_demand > 0:
                candidate = self._best_supplemental_candidate(article, state, remaining_demand)
                if candidate is None:
                    raise DataError(f"Unable to satisfy remaining demand for article {article}.")
                state.commit(candidate)
                remaining_demand -= candidate.take

                loc = candidate.loc
                route_hints = route_hints_by_floor.setdefault(loc.floor, [])
                if loc.node2d not in route_hints:
                    route_hints.append(loc.node2d)

        metadata = {
            "GTSP primary objective": f"{self.primary_objective(path):.2f}",
            "GTSP search objective": f"{self.search_objective(path):.2f}",
            "GTSP clusters": len(self.article_by_cluster),
            "GTSP points": len(self.points),
            "Candidate cap": self.max_candidates_per_article if self.max_candidates_per_article is not None else "all",
        }
        if notes:
            metadata.update(notes)

        return build_solution(
            algorithm=algorithm,
            picks_by_location=state.picks_by_location,
            demands=self.demands,
            relevant_locs=self.relevant_locs,
            loc_lookup=self.loc_lookup,
            weights=self.weights,
            solve_time=solve_time,
            phase_times=phase_times,
            notes=metadata,
            route_hints_by_floor=route_hints_by_floor,
            route_rebuild_threshold=route_rebuild_threshold,
        )

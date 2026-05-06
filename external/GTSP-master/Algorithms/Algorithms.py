from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - plotting is optional in headless runs
    plt = None

try:
    import seaborn as sns
except Exception:  # pragma: no cover - plotting is optional in headless runs
    sns = None


PairDistanceFn = Callable[[int, int], float]
EntryCostFn = Callable[[int], float]
PathCostFn = Callable[[Sequence[int]], float]


@dataclass(frozen=True)
class GTSPProblem:
    """Generalized TSP-style problem definition used by the warehouse adapter.

    Each point belongs to exactly one cluster. A path is valid when it chooses
    exactly one point from every cluster and orders those chosen points.
    """

    cluster_candidates: tuple[tuple[int, ...], ...]
    point_to_cluster: tuple[int, ...]
    distance_fn: PairDistanceFn | None = None
    entry_cost_fn: EntryCostFn | None = None
    objective_fn: PathCostFn | None = None
    name: str = "gtsp-problem"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def points(self) -> int:
        return len(self.point_to_cluster)

    @property
    def goods(self) -> int:
        return len(self.cluster_candidates)

    def cluster_for_point(self, point: int) -> int:
        if point < 0 or point >= self.points:
            raise IndexError(f"Point index {point} is out of range for {self.points} points.")
        return int(self.point_to_cluster[point])

    def candidate_points(self, cluster_index: int) -> tuple[int, ...]:
        if cluster_index < 0 or cluster_index >= self.goods:
            raise IndexError(f"Cluster index {cluster_index} is out of range for {self.goods} clusters.")
        return self.cluster_candidates[cluster_index]

    def random_point_for_cluster(self, cluster_index: int, rng: np.random.Generator) -> int:
        candidates = self.candidate_points(cluster_index)
        if not candidates:
            raise ValueError(f"Cluster {cluster_index} has no candidate points.")
        return int(rng.choice(candidates))

    def alternate_point(
        self,
        point: int,
        rng: np.random.Generator,
        *,
        exclude_current: bool = False,
    ) -> int:
        candidates = list(self.candidate_points(self.cluster_for_point(point)))
        if exclude_current and len(candidates) > 1:
            candidates = [candidate for candidate in candidates if candidate != point]
        return int(rng.choice(candidates))

    def random_path(self, rng: np.random.Generator) -> list[int]:
        path = [self.random_point_for_cluster(cluster_index, rng) for cluster_index in range(self.goods)]
        rng.shuffle(path)
        return [int(point) for point in path]

    def is_valid_path(self, path: Sequence[int]) -> bool:
        if len(path) != self.goods:
            return False
        seen_clusters: set[int] = set()
        for point in path:
            cluster = self.cluster_for_point(int(point))
            if cluster in seen_clusters:
                return False
            seen_clusters.add(cluster)
        return len(seen_clusters) == self.goods

    def route_cost(self, path: Sequence[int]) -> float:
        if not self.is_valid_path(path):
            return math.inf

        normalized_path = [int(point) for point in path]
        if self.objective_fn is not None:
            return float(self.objective_fn(normalized_path))

        if not normalized_path:
            return 0.0
        if self.distance_fn is None:
            raise ValueError("distance_fn must be provided when objective_fn is not set.")

        total = 0.0
        if self.entry_cost_fn is not None:
            total += float(self.entry_cost_fn(normalized_path[0]))
        for left, right in zip(normalized_path, normalized_path[1:]):
            total += float(self.distance_fn(left, right))
        if self.entry_cost_fn is not None:
            total += float(self.entry_cost_fn(normalized_path[-1]))
        else:
            total += float(self.distance_fn(normalized_path[-1], normalized_path[0]))
        return total


def load_problem(points: int, goods: int, filename: str | None = None) -> GTSPProblem:
    """Load the original NPY-backed toy data and expose it through GTSPProblem."""

    prefix = filename if filename is not None else ""
    base = Path(prefix) if prefix else Path(".")

    if filename is None:
        graph = np.load(f"Graph_{points}.npy", allow_pickle=True)
        goods_type = np.load(f"GoodsType_{points}_{goods}.npy", allow_pickle=True)
        type_list = np.load(f"TypeList_{points}_{goods}.npy", allow_pickle=True)
    else:
        graph = np.load(str(base) + "_Graph.npy", allow_pickle=True)
        goods_type = np.load(str(base) + "_GoodsType.npy", allow_pickle=True)
        type_list = np.load(str(base) + "_TypeList.npy", allow_pickle=True)

    cluster_candidates = tuple(tuple(int(point) for point in cluster) for cluster in goods_type.tolist())
    point_to_cluster = tuple(int(cluster) for cluster in type_list.tolist())

    def _cycle_cost(path: Sequence[int]) -> float:
        if not path:
            return 0.0
        total = 0.0
        for index in range(len(path)):
            total += float(graph[path[index], path[(index + 1) % len(path)]])
        return total

    return GTSPProblem(
        cluster_candidates=cluster_candidates,
        point_to_cluster=point_to_cluster,
        distance_fn=lambda left, right: float(graph[left, right]),
        objective_fn=_cycle_cost,
        name=f"legacy-{points}-{goods}",
        metadata={"points": points, "goods": goods},
    )


class Algorithm:
    def __init__(
        self,
        points: int | None = None,
        goods: int | None = None,
        filename: str | None = None,
        *,
        problem: GTSPProblem | None = None,
        seed: int | None = None,
    ) -> None:
        if problem is None:
            if points is None or goods is None:
                raise ValueError("Either problem or both points/goods must be supplied.")
            problem = load_problem(points, goods, filename=filename)

        self.problem = problem
        self.points = problem.points
        self.goods = problem.goods
        self.result: list[float] = []
        self.bestresult: list[float] = []
        self.rng = np.random.default_rng(seed)
        self.initial_path: list[int] | None = None
        self.seed_paths: list[list[int]] = []

    def fit(self, iteration: int) -> tuple[list[int], float]:
        raise NotImplementedError

    def set_initial_path(self, path: Sequence[int] | None) -> None:
        if path is None:
            self.initial_path = None
            return
        self.initial_path = [int(point) for point in path]

    def set_seed_paths(self, paths: Sequence[Sequence[int]]) -> None:
        self.seed_paths = [[int(point) for point in path] for path in paths if path]
        if self.seed_paths and self.initial_path is None:
            self.initial_path = self.seed_paths[0][:]

    def _generate_path(self) -> list[int]:
        if self.initial_path is not None:
            return [int(point) for point in self.initial_path]
        return self.problem.random_path(self.rng)

    def _calculate_singlecost(self, path: Sequence[int]) -> float:
        return self.problem.route_cost(path)

    def _swap_positions(self, path: Sequence[int]) -> list[int]:
        new_path = list(path)
        if len(new_path) < 2:
            return new_path
        left, right = sorted(int(index) for index in self.rng.choice(len(new_path), size=2, replace=False))
        new_path[left], new_path[right] = new_path[right], new_path[left]
        return new_path

    def _mutate_point_choice(
        self,
        path: Sequence[int],
        *,
        position: int | None = None,
        force_alternative: bool = False,
    ) -> list[int]:
        new_path = list(path)
        if not new_path:
            return new_path
        selected_position = int(self.rng.integers(0, len(new_path))) if position is None else int(position)
        new_path[selected_position] = self.problem.alternate_point(
            int(new_path[selected_position]),
            self.rng,
            exclude_current=force_alternative,
        )
        return new_path

    def _propose_neighbor(self, path: Sequence[int]) -> list[int]:
        candidate = self._swap_positions(path)
        if self.rng.random() < 0.7:
            candidate = self._mutate_point_choice(candidate, force_alternative=True)
        return candidate

    def show_result(self) -> None:
        if not self.result or plt is None:
            return
        if sns is not None:
            sns.set(style="white", palette="muted")
        x = [index + 1 for index in range(len(self.result))]
        plt.plot(x, self.result, label="iteration best")
        if self.bestresult:
            plt.plot(x[: len(self.bestresult)], self.bestresult, label="global best")
            plt.legend()
        plt.show()

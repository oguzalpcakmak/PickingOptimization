from __future__ import annotations

from collections import defaultdict
import math

from .Algorithms import Algorithm


DEPOT_SENTINEL = -1


class Antcolony(Algorithm):
    def set(
        self,
        *,
        colony_size: int = 25,
        alpha: float = 1.0,
        beta: float = 2.0,
        evaporation: float = 0.35,
        q: float = 100.0,
    ) -> tuple[int, float, float, float, float]:
        self.colony_size = colony_size
        self.alpha = alpha
        self.beta = beta
        self.evaporation = evaporation
        self.q = q
        return colony_size, alpha, beta, evaporation, q

    def _edge_cost(self, left: int, right: int) -> float:
        if left == DEPOT_SENTINEL:
            if self.problem.entry_cost_fn is None:
                return 1.0
            return float(self.problem.entry_cost_fn(right))
        if right == DEPOT_SENTINEL:
            if self.problem.entry_cost_fn is None:
                return 1.0
            return float(self.problem.entry_cost_fn(left))
        if self.problem.distance_fn is None:
            return 1.0
        return float(self.problem.distance_fn(left, right))

    def _pheromone_value(self, pheromone_delta: dict[tuple[int, int], float], left: int, right: int) -> float:
        return 1.0 + pheromone_delta.get((left, right), 0.0)

    def _roulette_index(self, weights: list[float]) -> int:
        total = sum(weights)
        if total <= 0.0:
            return int(self.rng.integers(0, len(weights)))
        threshold = float(self.rng.random()) * total
        cumulative = 0.0
        for index, weight in enumerate(weights):
            cumulative += weight
            if cumulative >= threshold:
                return index
        return len(weights) - 1

    def _construct_ant_path(
        self,
        pheromone_delta: dict[tuple[int, int], float],
        alpha: float,
        beta: float,
    ) -> list[int]:
        remaining_clusters = set(range(self.goods))
        path: list[int] = []
        current = DEPOT_SENTINEL

        while remaining_clusters:
            choices: list[tuple[int, int]] = []
            weights: list[float] = []
            for cluster in remaining_clusters:
                for point in self.problem.candidate_points(cluster):
                    edge_cost = max(self._edge_cost(current, int(point)), 1e-9)
                    pheromone = max(self._pheromone_value(pheromone_delta, current, int(point)), 1e-9)
                    desirability = 1.0 / edge_cost
                    choices.append((cluster, int(point)))
                    weights.append((pheromone**alpha) * (desirability**beta))

            if not choices:
                break

            selected_index = self._roulette_index(weights)
            cluster, point = choices[selected_index]
            path.append(point)
            remaining_clusters.remove(cluster)
            current = point

        return path

    def _evaporate(self, pheromone_delta: dict[tuple[int, int], float], evaporation: float) -> None:
        for edge in list(pheromone_delta):
            pheromone_delta[edge] *= (1.0 - evaporation)
            if pheromone_delta[edge] < 1e-6:
                del pheromone_delta[edge]

    def _deposit(
        self,
        pheromone_delta: dict[tuple[int, int], float],
        path: list[int],
        cost: float,
        q: float,
    ) -> None:
        if not path or not math.isfinite(cost):
            return
        deposit = q / max(cost, 1e-9)
        edges = [(DEPOT_SENTINEL, path[0]), *zip(path, path[1:]), (path[-1], DEPOT_SENTINEL)]
        for left, right in edges:
            pheromone_delta[(left, right)] += deposit
            pheromone_delta[(right, left)] += deposit

    def fit(self, iteration: int) -> tuple[list[int], float]:
        colony_size, alpha, beta, evaporation, q = self.set(
            colony_size=getattr(self, "colony_size", 25),
            alpha=getattr(self, "alpha", 1.0),
            beta=getattr(self, "beta", 2.0),
            evaporation=getattr(self, "evaporation", 0.35),
            q=getattr(self, "q", 100.0),
        )

        pheromone_delta: dict[tuple[int, int], float] = defaultdict(float)
        best_path: list[int] = []
        best_cost = math.inf

        if self.initial_path is not None:
            seeded_path = [int(point) for point in self.initial_path]
            seeded_cost = self._calculate_singlecost(seeded_path)
            self._deposit(pheromone_delta, seeded_path, seeded_cost, q * 5.0)
            if seeded_cost < best_cost:
                best_cost = seeded_cost
                best_path = seeded_path[:]

        for _ in range(iteration):
            paths: list[list[int]] = []
            costs: list[float] = []
            for _ in range(colony_size):
                path = self._construct_ant_path(pheromone_delta, alpha, beta)
                cost = self._calculate_singlecost(path)
                paths.append(path)
                costs.append(cost)

            self._evaporate(pheromone_delta, evaporation)
            for path, cost in zip(paths, costs):
                self._deposit(pheromone_delta, path, cost, q)

            current_best_index = min(range(len(costs)), key=lambda index: costs[index])
            current_best_cost = costs[current_best_index]
            current_best_path = paths[current_best_index][:]

            self.result.append(current_best_cost)
            if current_best_cost < best_cost:
                best_cost = current_best_cost
                best_path = current_best_path
            self.bestresult.append(best_cost)

        return best_path, best_cost

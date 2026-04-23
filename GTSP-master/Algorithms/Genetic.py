from __future__ import annotations

import math

import numpy as np

from .Algorithms import Algorithm


class Genetic(Algorithm):
    def set(
        self,
        population: int = 40,
        crossRate: float = 0.8,
        varyRate: float = 0.2,
        eliteFraction: float = 0.1,
    ) -> None:
        self.crossRate = crossRate
        self.varyRate = varyRate
        self.population_size = max(2, int(population))
        self.elite_count = max(1, int(round(self.population_size * eliteFraction)))
        self.population = self._generate_population(self.population_size)

    def _generate_population(self, size: int) -> list[list[int]]:
        population: list[list[int]] = []
        for path in self.seed_paths:
            if len(population) >= size:
                break
            population.append([int(point) for point in path])
        while len(population) < size:
            population.append(self.problem.random_path(self.rng))
        return population

    def _calculate_cost(self, population: list[list[int]] | None = None) -> list[float]:
        working_population = self.population if population is None else population
        return [self._calculate_singlecost(individual) for individual in working_population]

    def selection(self, costs: list[float]) -> list[list[int]]:
        fitness = np.array(
            [0.0 if not math.isfinite(cost) else 1.0 / max(cost, 1e-9) for cost in costs],
            dtype=float,
        )
        total_fitness = float(fitness.sum())
        if total_fitness <= 0.0:
            probabilities = np.full(len(costs), 1.0 / len(costs), dtype=float)
        else:
            probabilities = fitness / total_fitness

        draw_count = max(2, self.population_size - self.elite_count)
        chosen_indices = self.rng.choice(len(costs), size=draw_count, replace=True, p=probabilities)
        return [self.population[int(index)][:] for index in chosen_indices]

    def _make_child(
        self,
        primary: list[int],
        secondary: list[int],
        left: int,
        right: int,
    ) -> list[int]:
        child: list[int | None] = [None] * len(primary)
        covered_clusters: set[int] = set()
        for index in range(left, right + 1):
            point = int(primary[index])
            child[index] = point
            covered_clusters.add(self.problem.cluster_for_point(point))

        remainder = [
            int(point)
            for point in secondary
            if self.problem.cluster_for_point(int(point)) not in covered_clusters
        ]
        remainder_iter = iter(remainder)
        for index, point in enumerate(child):
            if point is None:
                child[index] = next(remainder_iter)
        return [int(point) for point in child]

    def _ordered_crossover(self, first: list[int], second: list[int]) -> tuple[list[int], list[int]]:
        if len(first) < 2:
            return first[:], second[:]
        left, right = sorted(int(index) for index in self.rng.choice(len(first), size=2, replace=False))
        return (
            self._make_child(first, second, left, right),
            self._make_child(second, first, left, right),
        )

    def _vary_individual(self, individual: list[int]) -> list[int]:
        candidate = individual[:]
        if len(candidate) >= 2 and self.rng.random() < self.varyRate:
            candidate = self._swap_positions(candidate)
        if self.rng.random() < self.varyRate:
            candidate = self._mutate_point_choice(candidate, force_alternative=True)
        return candidate

    def fit(self, iteration: int) -> tuple[list[int], float]:
        if not hasattr(self, "population") or not self.population:
            self.set()

        best_path: list[int] = []
        best_cost = math.inf

        for _ in range(iteration):
            costs = self._calculate_cost()
            ranked = sorted(zip(costs, self.population), key=lambda item: item[0])
            current_best_cost, current_best_path = ranked[0][0], ranked[0][1][:]

            self.result.append(current_best_cost)
            if current_best_cost < best_cost:
                best_cost = current_best_cost
                best_path = current_best_path[:]
            self.bestresult.append(best_cost)

            elites = [individual[:] for _, individual in ranked[: self.elite_count]]
            mating_pool = elites + self.selection(costs)
            next_population = elites[:]

            while len(next_population) < self.population_size:
                first = mating_pool[int(self.rng.integers(0, len(mating_pool)))]
                second = mating_pool[int(self.rng.integers(0, len(mating_pool)))]
                if self.rng.random() < self.crossRate:
                    child_a, child_b = self._ordered_crossover(first, second)
                else:
                    child_a, child_b = first[:], second[:]

                next_population.append(self._vary_individual(child_a))
                if len(next_population) < self.population_size:
                    next_population.append(self._vary_individual(child_b))

            self.population = next_population[: self.population_size]

        return best_path, best_cost

from __future__ import annotations

import math

from .Algorithms import Algorithm


class Annealing(Algorithm):
    def set(
        self,
        *,
        initial_temperature: float = 10.0,
        end_temperature: float = 0.1,
        cooling_rate: float = 0.99,
        inner_loops: int = 50,
    ) -> tuple[float, float, float, int]:
        self.initial_temperature = initial_temperature
        self.end_temperature = end_temperature
        self.cooling_rate = cooling_rate
        self.inner_loops = inner_loops
        return initial_temperature, end_temperature, cooling_rate, inner_loops

    def fit(self, iteration: int) -> tuple[list[int], float]:
        temperature, end_temperature, cooling_rate, inner_loops = self.set(
            initial_temperature=getattr(self, "initial_temperature", 10.0),
            end_temperature=getattr(self, "end_temperature", 0.1),
            cooling_rate=getattr(self, "cooling_rate", 0.99),
            inner_loops=getattr(self, "inner_loops", 50),
        )

        path = self._generate_path()
        current_cost = self._calculate_singlecost(path)
        best_path = path[:]
        best_cost = current_cost

        count = 0
        while temperature > end_temperature and count < iteration:
            count += 1
            iteration_best = current_cost
            for _ in range(inner_loops):
                candidate = self._propose_neighbor(path)
                candidate_cost = self._calculate_singlecost(candidate)
                if candidate_cost <= current_cost or self.metropolis(candidate_cost, current_cost, temperature):
                    path = candidate
                    current_cost = candidate_cost
                    if current_cost < best_cost:
                        best_cost = current_cost
                        best_path = path[:]
                if current_cost < iteration_best:
                    iteration_best = current_cost

            self.result.append(iteration_best)
            self.bestresult.append(best_cost)
            temperature *= cooling_rate

        return best_path, best_cost

    def metropolis(self, new_cost: float, current_cost: float, temperature: float, boltzmann: float = 1.0) -> bool:
        acceptance = math.exp(-(new_cost - current_cost) / (boltzmann * max(temperature, 1e-9)))
        return acceptance > float(self.rng.random())

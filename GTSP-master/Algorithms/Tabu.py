from __future__ import annotations

from collections import deque

from .Algorithms import Algorithm


class Tabu(Algorithm):
    def set(
        self,
        *,
        tabu_length: int | None = None,
        neighborhood_size: int | None = None,
    ) -> tuple[int, int]:
        self.tabulen = tabu_length if tabu_length is not None else max(5, self.goods // 3)
        self.neighborhood_size = neighborhood_size if neighborhood_size is not None else max(10, self.goods // 2)
        return self.tabulen, self.neighborhood_size

    def fit(self, iteration: int) -> tuple[list[int], float]:
        tabu_length, neighborhood_size = self.set(
            tabu_length=getattr(self, "tabulen", None),
            neighborhood_size=getattr(self, "neighborhood_size", None),
        )

        current_path = self._generate_path()
        current_cost = self._calculate_singlecost(current_path)
        best_path = current_path[:]
        best_cost = current_cost

        self.result = [current_cost]
        self.bestresult = [best_cost]

        tabu_list: deque[tuple[int, ...]] = deque([tuple(current_path)], maxlen=tabu_length)

        for _ in range(iteration):
            candidates: list[tuple[float, list[int]]] = []
            for _ in range(neighborhood_size):
                path = self._propose_neighbor(current_path)
                candidates.append((self._calculate_singlecost(path), path))
            candidates.sort(key=lambda item: item[0])

            chosen_path = candidates[0][1]
            chosen_cost = candidates[0][0]
            for cost, path in candidates:
                signature = tuple(path)
                if signature not in tabu_list or cost < best_cost - 1e-9:
                    chosen_path = path
                    chosen_cost = cost
                    break

            current_path = chosen_path
            current_cost = chosen_cost
            tabu_list.append(tuple(current_path))

            if current_cost < best_cost:
                best_cost = current_cost
                best_path = current_path[:]

            self.result.append(current_cost)
            self.bestresult.append(best_cost)

        return best_path, best_cost

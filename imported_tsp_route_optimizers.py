"""Adapters for the imported TSP heuristics in the repo.

These implementations are adapted from the educational repository
`3-heuristic-algorithms-in-Python-for-Travelling-Salesman-Problem-main`.
They are used here as route-only post-optimizers on top of the warehouse
allocation heuristics.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence, TypeVar


NodeT = TypeVar("NodeT")


def _build_distance_matrix(
    ordered_nodes: Sequence[NodeT],
    *,
    depot_cost: Callable[[NodeT], float],
    pair_cost: Callable[[NodeT, NodeT], float],
) -> list[list[float]]:
    size = len(ordered_nodes) + 1
    matrix = [[0.0] * size for _ in range(size)]

    for index, node in enumerate(ordered_nodes, start=1):
        cost = depot_cost(node)
        matrix[0][index] = cost
        matrix[index][0] = cost

    for left_index in range(1, size):
        left_node = ordered_nodes[left_index - 1]
        for right_index in range(left_index + 1, size):
            right_node = ordered_nodes[right_index - 1]
            cost = pair_cost(left_node, right_node)
            matrix[left_index][right_index] = cost
            matrix[right_index][left_index] = cost

    return matrix


def _tour_cost(order: Sequence[int], matrix: Sequence[Sequence[float]]) -> float:
    cost = 0.0
    for index in range(len(order)):
        cost += matrix[order[index]][order[(index + 1) % len(order)]]
    return cost


def _random_customer_order(size: int, rng: random.Random) -> list[int]:
    order = list(range(1, size + 1))
    rng.shuffle(order)
    return [0] + order


def _ordered_customers_from_seed(
    nodes: Sequence[NodeT],
    initial_route: Sequence[NodeT] | None,
) -> list[NodeT]:
    unique_nodes = list(dict.fromkeys(nodes))
    if initial_route:
        seen = set()
        ordered = []
        for node in initial_route:
            if node in unique_nodes and node not in seen:
                ordered.append(node)
                seen.add(node)
        for node in unique_nodes:
            if node not in seen:
                ordered.append(node)
        return ordered
    return unique_nodes


def _city_swap_improve(
    order: list[int],
    matrix: Sequence[Sequence[float]],
    *,
    passes: int,
) -> list[int]:
    current = list(order)
    current_cost = _tour_cost(current, matrix)

    for _ in range(max(1, passes)):
        improved = False
        for left in range(1, len(current) - 1):
            for right in range(left + 1, len(current)):
                candidate = list(current)
                candidate[left], candidate[right] = candidate[right], candidate[left]
                candidate_cost = _tour_cost(candidate, matrix)
                if candidate_cost + 1e-9 < current_cost:
                    current = candidate
                    current_cost = candidate_cost
                    improved = True
        if not improved:
            break
    return current


def _simulated_annealing_improve(
    order: list[int],
    matrix: Sequence[Sequence[float]],
    *,
    seed: int,
    start_temp: float,
    cooling_rate: float,
    temp_lower_bound: float,
    tolerance: float,
    inner_limit: int,
) -> list[int]:
    rng = random.Random(seed)
    current = list(order)
    current_cost = _tour_cost(current, matrix)
    best = list(current)
    best_cost = current_cost
    temperature = start_temp

    while temperature > temp_lower_bound:
        for _ in range(max(1, inner_limit)):
            left, right = sorted(rng.sample(range(1, len(current)), k=2))
            candidate = list(current)
            candidate[left], candidate[right] = candidate[right], candidate[left]
            candidate_cost = _tour_cost(candidate, matrix)
            delta = candidate_cost - current_cost

            if delta < 0 or rng.random() < math.exp(-delta / max(temperature, 1e-9)):
                current = candidate
                current_cost = candidate_cost
                if current_cost + 1e-9 < best_cost:
                    best = list(current)
                    best_cost = current_cost

            if abs(delta) < tolerance:
                break

        temperature *= cooling_rate

    return best


def _roulette_selection(
    population: Sequence[list[int]],
    costs: Sequence[float],
    *,
    pairs: int,
    rng: random.Random,
) -> list[list[int]]:
    ranked_unique: list[list[int]] = []
    ranked_fitness: list[float] = []
    seen: set[tuple[int, ...]] = set()
    for chromosome, cost in sorted(zip(population, costs), key=lambda item: item[1]):
        key = tuple(chromosome)
        if key in seen:
            continue
        seen.add(key)
        ranked_unique.append(list(chromosome))
        ranked_fitness.append(1.0 / max(cost, 1e-9))

    target_count = min(len(ranked_unique), max(2, 2 * pairs))
    if len(ranked_unique) <= target_count:
        return ranked_unique[:target_count]

    total_fitness = sum(ranked_fitness)
    parents: list[list[int]] = []
    parent_keys: set[tuple[int, ...]] = set()
    max_attempts = max(20, target_count * 20)
    attempts = 0

    while len(parents) < target_count and attempts < max_attempts:
        attempts += 1
        target = rng.uniform(0.0, total_fitness)
        cumulative = 0.0
        for index, chromosome in enumerate(ranked_unique):
            cumulative += ranked_fitness[index]
            if cumulative >= target:
                key = tuple(chromosome)
                if key not in parent_keys:
                    parents.append(list(chromosome))
                    parent_keys.add(key)
                break

    if len(parents) < target_count:
        for chromosome in ranked_unique:
            key = tuple(chromosome)
            if key in parent_keys:
                continue
            parents.append(list(chromosome))
            parent_keys.add(key)
            if len(parents) >= target_count:
                break
    return parents


def _dedupe_population(
    population: Sequence[list[int]],
    matrix: Sequence[Sequence[float]],
) -> list[list[int]]:
    ranked = sorted(population, key=lambda chromosome: _tour_cost(chromosome, matrix))
    unique: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    for chromosome in ranked:
        key = tuple(chromosome)
        if key in seen:
            continue
        seen.add(key)
        unique.append(list(chromosome))
    return unique


def _repair_child(child: list[int], donor_slice: Sequence[int], start: int) -> list[int]:
    child_len = len(child)
    donor_positions = set(range(start, start + len(donor_slice)))
    seen = set(donor_slice)
    unused = [gene for gene in range(1, child_len + 1) if gene not in seen]
    unused_iter = iter(unused)

    for index in range(child_len):
        if index in donor_positions:
            continue
        gene = child[index]
        if gene in seen:
            child[index] = next(unused_iter)
        else:
            seen.add(gene)
    return child


def _crossover(
    parent_a: Sequence[int],
    parent_b: Sequence[int],
    *,
    rng: random.Random,
) -> list[int]:
    child_len = len(parent_a) - 1
    left = rng.randrange(0, child_len)
    right = rng.randrange(left + 1, child_len + 1)

    donor_slice = list(parent_b[left + 1 : right + 1])
    child_customers = list(parent_a[1:])
    child_customers[left:right] = donor_slice
    child_customers = _repair_child(child_customers, donor_slice, left)
    return [0] + child_customers


def _mutate(order: list[int], *, rng: random.Random, mutation_probability: float) -> list[int]:
    candidate = list(order)
    if rng.random() <= mutation_probability:
        left = rng.randrange(1, len(candidate))
        right = rng.randrange(left, len(candidate))
        candidate[left : right + 1] = reversed(candidate[left : right + 1])
    return candidate


def _genetic_improve(
    order: list[int],
    matrix: Sequence[Sequence[float]],
    *,
    seed: int,
    generations: int,
    population_size: int,
    parent_pairs: int,
    crossover_probability: float,
    mutation_probability: float,
) -> list[int]:
    rng = random.Random(seed)
    customer_count = len(order) - 1

    population: list[list[int]] = [list(order)]
    seen = {tuple(order)}
    while len(population) < max(2, population_size):
        candidate = _random_customer_order(customer_count, rng)
        key = tuple(candidate)
        if key in seen:
            continue
        population.append(candidate)
        seen.add(key)

    population = _dedupe_population(population, matrix)
    while len(population) < max(2, population_size):
        candidate = _random_customer_order(customer_count, rng)
        if tuple(candidate) in {tuple(chromosome) for chromosome in population}:
            continue
        population.append(candidate)

    best = min(population, key=lambda chromosome: _tour_cost(chromosome, matrix))
    best_cost = _tour_cost(best, matrix)

    for _ in range(max(1, generations)):
        costs = [_tour_cost(chromosome, matrix) for chromosome in population]
        parents = _roulette_selection(population, costs, pairs=parent_pairs, rng=rng)

        children: list[list[int]] = []
        for index in range(1, len(parents), 2):
            parent_a = parents[index - 1]
            parent_b = parents[index]
            if rng.random() <= crossover_probability:
                child = _crossover(parent_a, parent_b, rng=rng)
            else:
                child = list(parent_a)
            children.append(_mutate(child, rng=rng, mutation_probability=mutation_probability))

        if not children:
            continue

        children.sort(key=lambda chromosome: _tour_cost(chromosome, matrix))
        survivors = sorted(population, key=lambda chromosome: _tour_cost(chromosome, matrix))
        survivor_count = max(1, len(population) - len(children))
        population = survivors[:survivor_count] + children[: len(population) - survivor_count]
        population = _dedupe_population(population, matrix)

        while len(population) < max(2, population_size):
            candidate = _random_customer_order(customer_count, rng)
            if tuple(candidate) in {tuple(chromosome) for chromosome in population}:
                continue
            population.append(candidate)

        population.sort(key=lambda chromosome: _tour_cost(chromosome, matrix))
        population = population[:population_size]

        current_best = population[0]
        current_best_cost = _tour_cost(current_best, matrix)
        if current_best_cost + 1e-9 < best_cost:
            best = list(current_best)
            best_cost = current_best_cost

    return best


def optimize_route_with_imported_tsp(
    nodes: Sequence[NodeT],
    *,
    initial_route: Sequence[NodeT] | None,
    optimizer: str,
    depot_cost: Callable[[NodeT], float],
    pair_cost: Callable[[NodeT, NodeT], float],
    seed: int = 0,
) -> list[NodeT]:
    ordered_nodes = _ordered_customers_from_seed(nodes, initial_route)
    if len(ordered_nodes) <= 1:
        return ordered_nodes

    matrix = _build_distance_matrix(
        ordered_nodes,
        depot_cost=depot_cost,
        pair_cost=pair_cost,
    )
    base_order = [0] + list(range(1, len(ordered_nodes) + 1))

    if optimizer == "imported_city_swap":
        improved_order = _city_swap_improve(base_order, matrix, passes=2)
    elif optimizer == "imported_simulated_annealing":
        improved_order = _simulated_annealing_improve(
            base_order,
            matrix,
            seed=seed,
            start_temp=30.0,
            cooling_rate=0.995,
            temp_lower_bound=0.25,
            tolerance=0.5,
            inner_limit=max(25, min(200, len(ordered_nodes))),
        )
    elif optimizer == "imported_genetic":
        improved_order = _genetic_improve(
            base_order,
            matrix,
            seed=seed,
            generations=30,
            population_size=18,
            parent_pairs=4,
            crossover_probability=0.75,
            mutation_probability=0.35,
        )
    else:
        raise ValueError(f"Unsupported imported TSP optimizer '{optimizer}'.")

    seen_indices: set[int] = set()
    repaired_order: list[int] = [0]
    for index in improved_order:
        if index == 0 or index in seen_indices:
            continue
        if 1 <= index <= len(ordered_nodes):
            repaired_order.append(index)
            seen_indices.add(index)
    for index in range(1, len(ordered_nodes) + 1):
        if index not in seen_indices:
            repaired_order.append(index)

    return [ordered_nodes[index - 1] for index in repaired_order if index != 0]

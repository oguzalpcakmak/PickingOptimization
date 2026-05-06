"""Real-operation baselines for benchmark reports.

The algorithmic reports compare solver outputs under the shared objective:

    distance + 15 * opened THMs + 30 * active floors

This module keeps the real picking references in one place so generated
comparison tables can include the operational baseline consistently.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from heuristic_common import ObjectiveWeights, floor_index, optimize_route


FULL_REAL_PICK_SOURCE = Path("data/real_pick/Grup_Toplama_Verisi_With_PickOrder.csv")
NEW_REAL_PICK_SOURCE = Path("data/new_data/PickData.csv")

# The historical full-data file was audited earlier: same-floor STEP_DIST values
# match the shared geometry, while cross-floor transitions are understated by
# this amount relative to the exact-style metric used in the reports.
FULL_REAL_CROSS_FLOOR_CORRECTION = 1095.50


def _objective(distance: float, thms: int, floors: int, weights: ObjectiveWeights) -> float:
    return (weights.distance * distance) + (weights.thm * thms) + (weights.floor * floors)


def full_data_recorded_baseline(
    *,
    source: Path = FULL_REAL_PICK_SOURCE,
    weights: ObjectiveWeights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0),
) -> dict[str, Any] | None:
    if not source.exists():
        return None

    start = time.perf_counter()
    rows: list[dict[str, str]] = []
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            if row.get("AREA") and row.get("AISLE") and row.get("COLUMN"):
                rows.append(row)
    if not rows:
        return None

    route_nodes_by_group: dict[tuple[str, str], set[tuple[str, int, int]]] = defaultdict(set)
    raw_distance = 0.0
    thms: set[str] = set()
    floors: set[str] = set()
    for row in rows:
        floor = row["AREA"].strip().upper()
        aisle = int(float(row["AISLE"]))
        column = int(float(row["COLUMN"]))
        route_key = (row.get("PICKER_CODE", "").strip(), row.get("PICKCAR_THM", "").strip())
        route_nodes_by_group[route_key].add((floor, aisle, column))
        raw_distance += float(row.get("STEP_DIST") or 0)
        if row.get("PICKED_THM"):
            thms.add(row["PICKED_THM"].strip())
        floors.add(floor)

    distance = round(raw_distance + FULL_REAL_CROSS_FLOOR_CORRECTION, 2)
    total_thms = len(thms)
    total_floors = len(floors)
    return {
        "dataset_slug": "old_full_data",
        "label": "Historical actual operation",
        "source": str(source),
        "method": "recorded CSV + exact-style cross-floor correction",
        "objective": round(_objective(distance, total_thms, total_floors, weights), 2),
        "distance": distance,
        "floors": total_floors,
        "thms": total_thms,
        "pick_rows": len(rows),
        "visited_nodes": sum(len(nodes) for nodes in route_nodes_by_group.values()),
        "solve_time": time.perf_counter() - start,
        "raw_recorded_distance": round(raw_distance, 2),
        "cross_floor_correction": FULL_REAL_CROSS_FLOOR_CORRECTION,
    }


def new_data_rerouted_baseline(
    *,
    source: Path = NEW_REAL_PICK_SOURCE,
    weights: ObjectiveWeights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0),
) -> dict[str, Any] | None:
    if not source.exists():
        return None

    start = time.perf_counter()
    rows: list[dict[str, str]] = []
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("FLOOR") and row.get("AISLE") and row.get("COLUMN"):
                rows.append(row)
    if not rows:
        return None

    nodes_by_floor: dict[str, set[tuple[int, int]]] = defaultdict(set)
    thms: set[str] = set()
    for row in rows:
        floor = row["FLOOR"].strip().upper()
        aisle = int(float(row["AISLE"]))
        column = int(float(row["COLUMN"]))
        nodes_by_floor[floor].add((aisle, column))
        if row.get("THM_ID"):
            thms.add(row["THM_ID"].strip())

    distance = 0.0
    visited_nodes = 0
    for floor in sorted(nodes_by_floor, key=floor_index):
        route, route_distance = optimize_route(nodes_by_floor[floor], use_regret=True, two_opt_passes=3)
        distance += route_distance
        visited_nodes += len(route)

    distance = round(distance, 2)
    total_thms = len(thms)
    total_floors = len(nodes_by_floor)
    return {
        "dataset_slug": "new_data",
        "label": "Real pick re-routed baseline",
        "source": str(source),
        "method": "actual selected locations re-routed with shared route builder",
        "objective": round(_objective(distance, total_thms, total_floors, weights), 2),
        "distance": distance,
        "floors": total_floors,
        "thms": total_thms,
        "pick_rows": len(rows),
        "visited_nodes": visited_nodes,
        "solve_time": time.perf_counter() - start,
    }


def get_real_pick_baseline(
    dataset_slug: str,
    *,
    weights: ObjectiveWeights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0),
) -> dict[str, Any] | None:
    if dataset_slug == "old_full_data":
        return full_data_recorded_baseline(weights=weights)
    if dataset_slug == "new_data":
        return new_data_rerouted_baseline(weights=weights)
    return None


def all_real_pick_baselines(
    *,
    weights: ObjectiveWeights = ObjectiveWeights(distance=1.0, thm=15.0, floor=30.0),
) -> list[dict[str, Any]]:
    baselines = [
        get_real_pick_baseline("old_full_data", weights=weights),
        get_real_pick_baseline("new_data", weights=weights),
    ]
    return [baseline for baseline in baselines if baseline is not None]


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize real-operation benchmark baselines.")
    parser.add_argument("--output", default="outputs/benchmark_outputs/real_pick_baselines/summary.json")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    args = parser.parse_args()

    weights = ObjectiveWeights(distance=args.distance_weight, thm=args.thm_weight, floor=args.floor_weight)
    baselines = all_real_pick_baselines(weights=weights)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(baselines, indent=2), encoding="utf-8")
    print(json.dumps(baselines, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

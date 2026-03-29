"""Hiyerarşik Ayrıştırma Heuristiği — Depo Toplama Optimizasyonu.

Gurobi gerektirmez. Saf Python. Beklenen süre: < 10 saniye.

Algoritma:
  Faz 1 — Kat Atama:
    1a. Tek katta bulunan ürünler → o kata sabitlenir
    1b. Birden fazla kattaki ürünler → en yoğun (en çok ürün atanmış) kata atanır
  Faz 2 — Kat İçi Alokasyon (her kat bağımsız):
    2a. Zorunlu toplama noktalarını belirle (tek lokasyonlu ürünler)
    2b. Açılan THM'lerdeki diğer ürünleri ara
    2c. Açılan koridor+bölgelerdeki (col 1-5, 6-10, 11-15, 16-20) ürünleri ara
    2d. Kalan ürünleri en yakın lokasyondan al
  Faz 3 — Kat İçi Rotalama:
    Her kat için nearest-neighbor + 2-opt
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


# ═══════════════════════════════════════════════════════════════════════
# DEPO GEOMETRİSİ
# ═══════════════════════════════════════════════════════════════════════

AISLE_WIDTH = 1.36
COLUMN_LENGTH = 2.90
SHELF_DEPTH = 1.16
CROSS_AISLE_WIDTH = 2.70
TOTAL_AISLES = 27
TOTAL_COLUMNS = 20
AISLE_PITCH = AISLE_WIDTH + (2 * SHELF_DEPTH)

CROSS_AISLE_1_Y = CROSS_AISLE_WIDTH / 2.0
CROSS_AISLE_2_Y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + (CROSS_AISLE_WIDTH / 2.0)
CROSS_AISLE_3_Y = (
    CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH
    + CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH
    + (CROSS_AISLE_WIDTH / 2.0)
)
CROSS_AISLE_CENTERS = (CROSS_AISLE_1_Y, CROSS_AISLE_2_Y, CROSS_AISLE_3_Y)

FLOOR_ORDER = ("MZN1", "MZN2", "MZN3", "MZN4", "MZN5", "MZN6")
ELEVATOR_AISLES = {1: 8, 2: 18}
STAIRS = (
    {"id": 1, "aisle1": 5,  "aisle2": 6,  "cross_aisle": 1},
    {"id": 2, "aisle1": 15, "aisle2": 16, "cross_aisle": 1},
    {"id": 3, "aisle1": 24, "aisle2": 25, "cross_aisle": 1},
    {"id": 4, "aisle1": 9,  "aisle2": 10, "cross_aisle": 2},
    {"id": 5, "aisle1": 19, "aisle2": 20, "cross_aisle": 2},
    {"id": 6, "aisle1": 4,  "aisle2": 5,  "cross_aisle": 3},
    {"id": 7, "aisle1": 14, "aisle2": 15, "cross_aisle": 3},
    {"id": 8, "aisle1": 23, "aisle2": 24, "cross_aisle": 3},
)

DEPOT_ID = "__DEPOT__"


def _floor_index(floor: str) -> int:
    return FLOOR_ORDER.index(floor) + 1


def _reversed_aisle(aisle: int) -> int:
    return TOTAL_AISLES - aisle + 1


def _x_coord(aisle: int) -> float:
    return (SHELF_DEPTH + AISLE_WIDTH / 2.0) + ((_reversed_aisle(aisle) - 1) * AISLE_PITCH)


def _y_coord(column: int) -> float:
    if column <= 10:
        return CROSS_AISLE_WIDTH + ((column - 0.5) * COLUMN_LENGTH)
    return (CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH
            + CROSS_AISLE_WIDTH + ((column - 10 - 0.5) * COLUMN_LENGTH))


def _column_zone(column: int) -> int:
    """Kolon bölgesi: 1-5→1, 6-10→2, 11-15→3, 16-20→4."""
    return (column - 1) // 5 + 1


def _same_floor_dist(ai_a: int, co_a: int, ai_b: int, co_b: int) -> float:
    x1, y1 = _x_coord(ai_a), _y_coord(co_a)
    x2, y2 = _x_coord(ai_b), _y_coord(co_b)
    if ai_a == ai_b:
        return abs(y1 - y2)
    return min(abs(y1 - cy) + abs(x1 - x2) + abs(cy - y2) for cy in CROSS_AISLE_CENTERS)


def _stair_pos(sid: int) -> tuple[float, float]:
    s = next(st for st in STAIRS if st["id"] == sid)
    x = (_x_coord(s["aisle1"]) + _x_coord(s["aisle2"])) / 2.0
    if s["cross_aisle"] == 1:
        y = CROSS_AISLE_WIDTH
    elif s["cross_aisle"] == 2:
        y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH
    else:
        y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH
    return x, y


def _nearest_elevator(aisle: int) -> int:
    return 1 if abs(aisle - ELEVATOR_AISLES[1]) <= abs(aisle - ELEVATOR_AISLES[2]) else 2


def _nearest_stair_to_elev(elev: int) -> int:
    ex = _x_coord(ELEVATOR_AISLES[elev])
    best, bd = 1, math.inf
    for s in STAIRS:
        if s["cross_aisle"] != 1:
            continue
        sx, _ = _stair_pos(s["id"])
        d = abs(sx - ex)
        if d < bd:
            bd, best = d, s["id"]
    return best


def _entry_exit_dist(aisle: int, column: int) -> float:
    elev = _nearest_elevator(aisle)
    stair = _nearest_stair_to_elev(elev)
    sx, _ = _stair_pos(stair)
    ex = _x_coord(ELEVATOR_AISLES[elev])
    se_dist = abs(sx - ex) + CROSS_AISLE_WIDTH
    horiz = abs(aisle - ELEVATOR_AISLES[elev]) * AISLE_PITCH
    if column <= 10:
        vert = CROSS_AISLE_WIDTH + ((column - 0.5) * COLUMN_LENGTH)
    else:
        vert = (CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH
                + CROSS_AISLE_WIDTH + ((column - 10 - 0.5) * COLUMN_LENGTH))
    return se_dist + horiz + vert


# ═══════════════════════════════════════════════════════════════════════
# VERİ YAPILARI VE CSV YÜKLEME
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Loc:
    """Tam stok lokasyonu."""
    lid: str
    thm_id: str
    article: int
    floor: str
    aisle: int
    side: str
    column: int
    shelf: int
    stock: int


class DataError(ValueError):
    pass


def _safe_int(v: Any) -> int | None:
    try:
        t = str(v).strip()
    except Exception:
        return None
    if not t:
        return None
    try:
        return int(t)
    except ValueError:
        return None


def _norm_floor(v: Any) -> str | None:
    if v is None:
        return None
    f = str(v).strip().upper()
    return f if f in FLOOR_ORDER else None


def _norm_side(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip().upper()
    if s.startswith("L"):
        return "L"
    if s.startswith("R"):
        return "R"
    return None


def load_demands(path: str | Path) -> dict[int, int]:
    totals: dict[int, int] = defaultdict(int)
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            art = _safe_int(row.get("ARTICLE_CODE"))
            amt = _safe_int(row.get("AMOUNT"))
            if art is None or amt is None:
                continue
            if amt < 0:
                raise DataError(f"Eksi talep: ürün {art}")
            totals[art] += amt
    return dict(totals)


def load_stock(path: str | Path) -> list[Loc]:
    agg: dict[tuple, int] = defaultdict(int)
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            art = _safe_int(row.get("ARTICLE_CODE"))
            ai = _safe_int(row.get("AISLE"))
            co = _safe_int(row.get("COLUMN"))
            sh = _safe_int(row.get("SHELF"))
            st = _safe_int(row.get("STOCK"))
            fl = _norm_floor(row.get("FLOOR"))
            sd = _norm_side(row.get("RIGHT_OR_LEFT") or row.get("LEFT_OR_RIGHT"))
            thm = str(row.get("THM_ID", "")).strip()
            if None in (art, ai, co, sh, st) or fl is None or sd is None or not thm:
                continue
            if st <= 0:
                continue
            if not (1 <= ai <= TOTAL_AISLES) or not (1 <= co <= TOTAL_COLUMNS):
                continue
            agg[(thm, art, fl, ai, sd, co, sh)] += st

    locs = []
    for i, (key, stk) in enumerate(sorted(agg.items()), 1):
        thm, art, fl, ai, sd, co, sh = key
        locs.append(Loc(f"j{i:05d}", thm, art, fl, ai, sd, co, sh, stk))
    return locs


# ═══════════════════════════════════════════════════════════════════════
# FAZ 1: KAT ATAMA
# ═══════════════════════════════════════════════════════════════════════


def phase1_floor_assignment(
    demands: dict[int, int],
    all_locs: list[Loc],
    floor_filter: set[str] | None = None,
) -> dict[str, dict[int, int]]:
    """Her ürünü bir veya birden fazla kata atar.

    Dönüş: {floor: {article: quantity}} — her kat için toplanacak ürün ve miktar.
    """
    # Ürün başına kat→stok haritası
    art_floor_stock: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for loc in all_locs:
        if floor_filter and loc.floor not in floor_filter:
            continue
        if loc.article not in demands:
            continue
        art_floor_stock[loc.article][loc.floor] += loc.stock

    # Fizibilite kontrolü
    for art, demand in demands.items():
        total = sum(art_floor_stock[art].values())
        if total < demand:
            raise DataError(
                f"Ürün {art}: talep={demand}, toplam stok={total} — yetersiz."
            )

    # Kat atamaları
    floor_assign: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    floor_density: dict[str, int] = defaultdict(int)  # kata atanan ürün sayısı

    # ── Adım 1a: Tek katta bulunan ürünler → sabit atama ──
    single_floor_arts = []
    multi_floor_arts = []

    for art, demand in sorted(demands.items()):
        floors_with_stock = {
            fl: stk for fl, stk in art_floor_stock[art].items() if stk > 0
        }
        if len(floors_with_stock) == 1:
            single_floor_arts.append(art)
        else:
            multi_floor_arts.append(art)

    for art in single_floor_arts:
        fl = next(iter(art_floor_stock[art]))
        floor_assign[fl][art] = demands[art]
        floor_density[fl] += 1

    print(f"    Tek katlı ürün: {len(single_floor_arts)}, "
          f"çok katlı ürün: {len(multi_floor_arts)}")

    # ── Adım 1b: Çok katlı ürünler → en yoğun kata ──
    # Az alternatifi olan önce (zor ürünler önce)
    multi_floor_arts.sort(
        key=lambda a: len([f for f, s in art_floor_stock[a].items() if s > 0])
    )

    for art in multi_floor_arts:
        remaining = demands[art]
        avail_floors = {
            fl: stk for fl, stk in art_floor_stock[art].items() if stk > 0
        }
        # Yoğunluk azalan, stok azalan sırada dene
        sorted_floors = sorted(
            avail_floors.keys(),
            key=lambda fl: (-floor_density[fl], -avail_floors[fl]),
        )
        for fl in sorted_floors:
            if remaining <= 0:
                break
            take = min(remaining, avail_floors[fl])
            if take > 0:
                floor_assign[fl][art] += take
                remaining -= take
                floor_density[fl] += 1

    return dict(floor_assign)


# ═══════════════════════════════════════════════════════════════════════
# FAZ 2: KAT İÇİ ALOKASYON
# ═══════════════════════════════════════════════════════════════════════


def phase2_floor_allocation(
    floor: str,
    art_demands: dict[int, int],
    floor_locs: list[Loc],
) -> dict[str, int]:
    """Bir kattaki ürünleri lokasyonlara aloke eder.

    Döndürür: {location_id: miktar}
    """
    # Ürün → lokasyon listesi
    locs_by_art: dict[int, list[Loc]] = defaultdict(list)
    for loc in floor_locs:
        if loc.article in art_demands:
            locs_by_art[loc.article].append(loc)

    picks: dict[str, int] = {}
    used_stock: dict[str, int] = defaultdict(int)
    opened_thms: set[str] = set()
    visited_aisles: set[int] = set()
    active_zones: set[tuple[int, int]] = set()  # (aisle, zone)

    def _try_alloc(art: int, remaining: int, candidates: list[Loc]) -> int:
        """Aday listesinden mümkün olduğunca aloke et. Kalan miktarı döndür."""
        nonlocal picks, used_stock, opened_thms, visited_aisles, active_zones
        for loc in candidates:
            if remaining <= 0:
                break
            avail = loc.stock - used_stock[loc.lid]
            if avail <= 0:
                continue
            take = min(remaining, avail)
            picks[loc.lid] = picks.get(loc.lid, 0) + take
            used_stock[loc.lid] += take
            remaining -= take
            opened_thms.add(loc.thm_id)
            visited_aisles.add(loc.aisle)
            active_zones.add((loc.aisle, _column_zone(loc.column)))
        return remaining

    # ── Adım 2a: Zorunlu (tek lokasyonlu) ürünler ──
    mandatory_arts = []
    flexible_arts = []
    for art, demand in art_demands.items():
        candidates = locs_by_art.get(art, [])
        if len(candidates) <= 1:
            mandatory_arts.append(art)
        else:
            flexible_arts.append(art)

    for art in mandatory_arts:
        candidates = locs_by_art.get(art, [])
        _try_alloc(art, art_demands[art], candidates)

    # ── Adım 2b: Esnek ürünler — öncelik sırasıyla ──
    for art in flexible_arts:
        remaining = art_demands[art]
        candidates = locs_by_art.get(art, [])

        # Öncelik 1: Zaten açılmış THM'lerdeki lokasyonlar
        thm_locs = [l for l in candidates if l.thm_id in opened_thms]
        remaining = _try_alloc(art, remaining, thm_locs)
        if remaining <= 0:
            continue

        # Öncelik 2: Zaten aktif bölgelerdeki lokasyonlar (aisle+zone)
        zone_locs = [
            l for l in candidates
            if (l.aisle, _column_zone(l.column)) in active_zones
               and l.lid not in picks
        ]
        remaining = _try_alloc(art, remaining, zone_locs)
        if remaining <= 0:
            continue

        # Öncelik 3: Zaten ziyaret edilen koridorlardaki lokasyonlar
        aisle_locs = [
            l for l in candidates
            if l.aisle in visited_aisles and l.lid not in picks
        ]
        remaining = _try_alloc(art, remaining, aisle_locs)
        if remaining <= 0:
            continue

        # Öncelik 4: Kalan herhangi bir lokasyon
        rest = [l for l in candidates if l.lid not in picks]
        remaining = _try_alloc(art, remaining, rest)

    return picks


# ═══════════════════════════════════════════════════════════════════════
# FAZ 3: KAT İÇİ ROTALAMA (Nearest-Neighbor + 2-opt)
# ═══════════════════════════════════════════════════════════════════════


def _nn_route(
    nodes: list[tuple[int, int]],
    entry_aisle: int,
    entry_col: int,
) -> list[tuple[int, int]]:
    """Nearest-neighbor rota: (aisle, column) listesi üzerinde."""
    if len(nodes) <= 1:
        return list(nodes)
    unvisited = set(range(len(nodes)))
    route = []
    cur_ai, cur_co = entry_aisle, entry_col

    while unvisited:
        best_i, best_d = -1, math.inf
        for i in unvisited:
            d = _same_floor_dist(cur_ai, cur_co, nodes[i][0], nodes[i][1])
            if d < best_d:
                best_d, best_i = d, i
        route.append(nodes[best_i])
        cur_ai, cur_co = nodes[best_i]
        unvisited.remove(best_i)
    return route


def _two_opt(
    route: list[tuple[int, int]],
    max_seconds: float = 15.0,
) -> list[tuple[int, int]]:
    """2-opt iyileştirme."""
    if len(route) <= 3:
        return route
    route = list(route)
    n = len(route)
    t0 = time.perf_counter()
    improved = True
    while improved:
        if time.perf_counter() - t0 > max_seconds:
            break
        improved = False
        for i in range(n - 1):
            for j in range(i + 2, n):
                ai, ci = route[i]
                bi, bj = route[i + 1] if i + 1 < n else route[0], route[i + 1] if i + 1 < n else route[0]
                a = route[i]
                b = route[i + 1]
                c = route[j]
                d = route[j + 1] if j + 1 < n else route[0]

                old = (_same_floor_dist(a[0], a[1], b[0], b[1])
                       + _same_floor_dist(c[0], c[1], d[0], d[1]))
                new = (_same_floor_dist(a[0], a[1], c[0], c[1])
                       + _same_floor_dist(b[0], b[1], d[0], d[1]))
                if new < old - 1e-9:
                    route[i + 1:j + 1] = reversed(route[i + 1:j + 1])
                    improved = True
    return route


def _route_distance(route: list[tuple[int, int]], entry_ai: int, entry_co: int) -> float:
    """Rota toplam mesafesi (entry → route → entry)."""
    if not route:
        return 0.0
    d = _same_floor_dist(entry_ai, entry_co, route[0][0], route[0][1])
    for i in range(len(route) - 1):
        d += _same_floor_dist(route[i][0], route[i][1], route[i + 1][0], route[i + 1][1])
    d += _same_floor_dist(route[-1][0], route[-1][1], entry_ai, entry_co)
    return d


def phase3_floor_routing(
    picks: dict[str, int],
    loc_lookup: dict[str, Loc],
) -> list[tuple[int, int]]:
    """Seçilen lokasyonlardan fiziksel düğümleri çıkarıp rota oluşturur."""
    nodes_set: set[tuple[int, int]] = set()
    for lid in picks:
        loc = loc_lookup[lid]
        nodes_set.add((loc.aisle, loc.column))

    nodes = sorted(nodes_set)
    if not nodes:
        return []

    # Giriş noktası: asansöre en yakın koridorun başı
    entry_aisle = min(nodes, key=lambda n: n[0])[0]
    entry_col = 1

    route = _nn_route(nodes, entry_aisle, entry_col)
    route = _two_opt(route, max_seconds=10.0)
    return route


# ═══════════════════════════════════════════════════════════════════════
# ANA ÇÖZÜCÜ
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class FloorResult:
    floor: str
    picks: dict[str, int]
    route: list[tuple[int, int]]
    route_distance: float
    opened_thms: set[str]
    visited_nodes: int


@dataclass
class Solution:
    floor_results: list[FloorResult]
    total_distance: float
    total_thms: int
    total_floors: int
    total_picks: int
    solve_time: float
    phase_times: dict[str, float]
    objective_value: float
    demands: dict[int, int]
    floor_assignments: dict[str, dict[int, int]]
    relevant_locs: list[Loc]
    loc_lookup: dict[str, Loc]


def solve(
    order_path: str | Path,
    stock_path: str | Path,
    *,
    floors: Iterable[str] | None = None,
    articles: Iterable[int] | None = None,
    distance_weight: float = 1.0,
    thm_weight: float = 15.0,
    floor_weight: float = 30.0,
) -> Solution:
    t_total = time.perf_counter()
    phase_times: dict[str, float] = {}

    # Veri yükleme
    t0 = time.perf_counter()
    demands = load_demands(order_path)
    all_locs = load_stock(stock_path)

    floor_filter = {s.upper() for s in floors} if floors else None
    if articles:
        art_set = {int(a) for a in articles}
        demands = {a: d for a, d in demands.items() if a in art_set}

    # Sadece talep edilen ürünlerin lokasyonlarını tut
    relevant_locs = [l for l in all_locs if l.article in demands]
    if floor_filter:
        relevant_locs = [l for l in relevant_locs if l.floor in floor_filter]

    loc_lookup = {l.lid: l for l in relevant_locs}
    phase_times["veri_yukleme"] = time.perf_counter() - t0
    print(f"  Veri: {len(demands)} ürün, {len(relevant_locs)} lokasyon "
          f"({phase_times['veri_yukleme']:.2f}s)")

    # ── FAZ 1: Kat atama ──
    t0 = time.perf_counter()
    print("\n  [Faz 1] Kat atama...")
    floor_assignments = phase1_floor_assignment(demands, relevant_locs, floor_filter)
    phase_times["kat_atama"] = time.perf_counter() - t0

    for fl in sorted(floor_assignments, key=_floor_index):
        arts = floor_assignments[fl]
        total_items = sum(arts.values())
        print(f"    {fl}: {len(arts)} ürün, {total_items} adet")

    # ── FAZ 2 & 3: Her kat için alokasyon + rotalama ──
    floor_results: list[FloorResult] = []

    for fl in sorted(floor_assignments, key=_floor_index):
        art_demands = floor_assignments[fl]
        fl_locs = [l for l in relevant_locs if l.floor == fl]

        # Faz 2: Alokasyon
        t0 = time.perf_counter()
        picks = phase2_floor_allocation(fl, art_demands, fl_locs)
        alloc_time = time.perf_counter() - t0

        # Faz 3: Rotalama
        t0 = time.perf_counter()
        route = phase3_floor_routing(picks, loc_lookup)
        entry_ai = min((n[0] for n in route), default=1)
        rdist = _route_distance(route, entry_ai, 1)
        route_time = time.perf_counter() - t0

        opened = {loc_lookup[lid].thm_id for lid in picks}
        fr = FloorResult(fl, picks, route, rdist, opened, len(route))
        floor_results.append(fr)

        phase_times[f"{fl}_alokasyon"] = alloc_time
        phase_times[f"{fl}_rotalama"] = route_time
        print(f"\n  [Faz 2-3] {fl}: {len(picks)} lokasyon, "
              f"{len(opened)} THM, {len(route)} düğüm, "
              f"mesafe={rdist:.1f}m ({alloc_time + route_time:.2f}s)")

    # Toplam metrikleri hesapla
    total_dist = sum(fr.route_distance for fr in floor_results)
    # Katlar arası giriş/çıkış mesafelerini ekle
    for fr in floor_results:
        for ai, co in fr.route:
            total_dist += _entry_exit_dist(ai, co) * 2  # gidiş + dönüş

    all_thms: set[str] = set()
    total_picks = 0
    for fr in floor_results:
        all_thms |= fr.opened_thms
        total_picks += len(fr.picks)

    total_time = time.perf_counter() - t_total
    phase_times["toplam"] = total_time

    obj = (distance_weight * total_dist
           + thm_weight * len(all_thms)
           + floor_weight * len(floor_results))

    return Solution(
        floor_results=floor_results,
        total_distance=total_dist,
        total_thms=len(all_thms),
        total_floors=len(floor_results),
        total_picks=total_picks,
        solve_time=total_time,
        phase_times=phase_times,
        objective_value=obj,
        demands=dict(demands),
        floor_assignments={fl: dict(arts) for fl, arts in floor_assignments.items()},
        relevant_locs=list(relevant_locs),
        loc_lookup=dict(loc_lookup),
    )


# ═══════════════════════════════════════════════════════════════════════
# CSV ÇIKTI VE RAPORLAMA
# ═══════════════════════════════════════════════════════════════════════


def _build_node_id_map(locs: Iterable[Loc]) -> dict[tuple[str, int, int], str]:
    node_keys = sorted(
        {(loc.floor, loc.aisle, loc.column) for loc in locs},
        key=lambda key: (_floor_index(key[0]), key[1], key[2]),
    )
    return {key: f"n{i:05d}" for i, key in enumerate(node_keys, 1)}


def write_pick_csv(sol: Solution, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for fr in sol.floor_results:
        # Rota sırası: (aisle, column) → sıra numarası
        route_pos = {node: i + 1 for i, node in enumerate(fr.route)}
        for lid, qty in fr.picks.items():
            loc = sol.loc_lookup[lid]
            pos = route_pos.get((loc.aisle, loc.column), 999)
            rows.append({
                "PICKER_ID": f"PICKER_{loc.floor}",
                "THM_ID": loc.thm_id,
                "ARTICLE_CODE": loc.article,
                "FLOOR": loc.floor,
                "AISLE": loc.aisle,
                "COLUMN": loc.column,
                "SHELF": loc.shelf,
                "LEFT_OR_RIGHT": loc.side,
                "AMOUNT": qty,
                "PICKCAR_ID": f"PICKCAR_{loc.floor}",
                "PICK_ORDER": pos,
            })

    rows.sort(key=lambda r: (
        _floor_index(str(r["FLOOR"])), r["PICK_ORDER"],
        r["AISLE"], r["COLUMN"], r["SHELF"],
    ))

    fields = [
        "PICKER_ID", "THM_ID", "ARTICLE_CODE", "FLOOR", "AISLE",
        "COLUMN", "SHELF", "LEFT_OR_RIGHT", "AMOUNT", "PICKCAR_ID",
        "PICK_ORDER",
    ]
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return out


def write_alternative_locations_csv(sol: Solution, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    node_id_map = _build_node_id_map(sol.relevant_locs)
    picked_qty_by_lid: dict[str, int] = {}
    active_nodes: set[tuple[str, int, int]] = set()
    active_thms: set[str] = set()
    pick_order_by_node: dict[tuple[str, int, int], int] = {}

    for fr in sol.floor_results:
        active_thms |= fr.opened_thms
        route_pos = {node: i + 1 for i, node in enumerate(fr.route)}
        for aisle, column in fr.route:
            active_nodes.add((fr.floor, aisle, column))
            pick_order_by_node[(fr.floor, aisle, column)] = route_pos[(aisle, column)]
        for lid, qty in fr.picks.items():
            picked_qty_by_lid[lid] = picked_qty_by_lid.get(lid, 0) + qty

    floor_assigned = defaultdict(int)
    for floor, articles in sol.floor_assignments.items():
        for article, qty in articles.items():
            floor_assigned[(floor, article)] += qty

    rows: list[dict[str, Any]] = []
    for loc in sol.relevant_locs:
        node_key = (loc.floor, loc.aisle, loc.column)
        picked_qty = picked_qty_by_lid.get(loc.lid, 0)
        row = {
            "ARTICLE_CODE": loc.article,
            "ARTICLE_DEMAND": sol.demands[loc.article],
            "FLOOR_ASSIGNED_DEMAND": floor_assigned[(loc.floor, loc.article)],
            "LOCATION_ID": loc.lid,
            "THM_ID": loc.thm_id,
            "FLOOR": loc.floor,
            "AISLE": loc.aisle,
            "COLUMN": loc.column,
            "SHELF": loc.shelf,
            "LEFT_OR_RIGHT": loc.side,
            "AVAILABLE_STOCK": loc.stock,
            "NODE_ID": node_id_map[node_key],
            "NODE_VISITED": 1 if node_key in active_nodes else 0,
            "THM_OPENED": 1 if loc.thm_id in active_thms else 0,
            "IS_SELECTED": 1 if picked_qty > 0 else 0,
            "PICKED_AMOUNT": picked_qty,
            "PICK_ORDER": pick_order_by_node.get(node_key, ""),
        }
        rows.append(row)

    rows.sort(key=lambda r: (
        int(r["ARTICLE_CODE"]),
        -int(r["IS_SELECTED"]),
        int(r["PICK_ORDER"]) if str(r["PICK_ORDER"]).strip() else 10**9,
        _floor_index(str(r["FLOOR"])),
        int(r["AISLE"]),
        int(r["COLUMN"]),
        int(r["SHELF"]),
        str(r["LEFT_OR_RIGHT"]),
        str(r["THM_ID"]),
        str(r["LOCATION_ID"]),
    ))

    fields = [
        "ARTICLE_CODE",
        "ARTICLE_DEMAND",
        "FLOOR_ASSIGNED_DEMAND",
        "LOCATION_ID",
        "THM_ID",
        "FLOOR",
        "AISLE",
        "COLUMN",
        "SHELF",
        "LEFT_OR_RIGHT",
        "AVAILABLE_STOCK",
        "NODE_ID",
        "NODE_VISITED",
        "THM_OPENED",
        "IS_SELECTED",
        "PICKED_AMOUNT",
        "PICK_ORDER",
    ]
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return out


def print_report(sol: Solution) -> None:
    print()
    print("=" * 65)
    print("  HİYERARŞİK AYRIŞTIRMA HEURİSTİĞİ — SONUÇLAR")
    print("=" * 65)
    print()
    print(f"  Amaç fonksiyonu:             {sol.objective_value:.2f}")
    print(f"  Toplam mesafe:               {sol.total_distance:.2f} m")
    print(f"  Girilen kat sayısı:          {sol.total_floors}")
    print(f"  Açılan THM sayısı:           {sol.total_thms}")
    print(f"  Toplam alokasyon satırı:     {sol.total_picks}")
    print()
    print("  Kat Detayları:")
    for fr in sol.floor_results:
        print(f"    {fr.floor}: {len(fr.picks)} lokasyon, "
              f"{len(fr.opened_thms)} THM, "
              f"{fr.visited_nodes} düğüm, "
              f"mesafe={fr.route_distance:.1f}m")
    print()
    print("  Faz Süreleri:")
    for phase, t in sol.phase_times.items():
        if phase == "toplam":
            continue
        print(f"    {phase:25s}  {t:.4f} s")
    print()
    ok = "✓ 2 dakika altında" if sol.solve_time < 120 else "✗ 2 dakikayı aştı!"
    print(f"  TOPLAM SÜRE: {sol.solve_time:.2f} saniye — {ok}")
    print("=" * 65)


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hiyerarşik Ayrıştırma Heuristiği — Depo Toplama",
    )
    parser.add_argument("--orders", default="PickOrder.csv")
    parser.add_argument("--stock", default="StockData.csv")
    parser.add_argument("--floors", default=None,
                        help="Kat filtresi: MZN1 veya MZN1,MZN2")
    parser.add_argument("--articles", default=None,
                        help="Ürün filtresi: 258,376,471")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=15.0)
    parser.add_argument("--floor-weight", type=float, default=30.0)
    parser.add_argument(
        "--output", "--pick-data-output",
        dest="pick_data_output",
        default="PickDataOutput_Heuristic.csv",
        help="Pick CSV çıktısı. Exact modelle aynı kolon yapısını kullanır.",
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput_Heuristic.csv",
        help="Alternatif lokasyon CSV çıktısı. Boş string verilirse kapatılır.",
    )
    args = parser.parse_args(argv)

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  HİYERARŞİK AYRIŞTIRMA HEURİSTİĞİ v1.0               ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    floors = [t.strip().upper() for t in args.floors.split(",")] if args.floors else None
    articles = [int(t.strip()) for t in args.articles.split(",")] if args.articles else None

    sol = solve(
        args.orders, args.stock,
        floors=floors, articles=articles,
        distance_weight=args.distance_weight,
        thm_weight=args.thm_weight,
        floor_weight=args.floor_weight,
    )
    print_report(sol)

    if args.pick_data_output:
        p = write_pick_csv(sol, args.pick_data_output)
        print(f"\nÇıktı yazıldı: {p}")
    if args.alternative_locations_output:
        p_alt = write_alternative_locations_csv(sol, args.alternative_locations_output)
        print(f"Alternatif lokasyonlar yazıldı: {p_alt}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

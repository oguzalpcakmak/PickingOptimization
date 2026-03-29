"""Gurobi model builder for the warehouse picking formulation in Model.tex.

The implementation follows the variables and constraints in Model.tex as
closely as possible, with one practical correction for the routing layer:
an explicit virtual depot is added so the MTZ tour constraints are well posed.
Without that anchor node, the textbook MTZ formulation in the TeX file would
not define a feasible closed tour for arbitrary subsets of visited nodes.

The sample CSVs are also not globally feasible as-is: some ordered articles do
not exist in the stock file. This module validates that upfront and provides
helpers for building smaller, feasible test instances such as "one floor and a
few items", which is the next planned step for this project.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import gurobipy as gp
    from gurobipy import GRB
except ImportError:  # pragma: no cover - handled by runtime guard
    gp = None
    GRB = None


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
    CROSS_AISLE_WIDTH
    + 10 * COLUMN_LENGTH
    + CROSS_AISLE_WIDTH
    + 10 * COLUMN_LENGTH
    + (CROSS_AISLE_WIDTH / 2.0)
)
CROSS_AISLE_CENTERS = (CROSS_AISLE_1_Y, CROSS_AISLE_2_Y, CROSS_AISLE_3_Y)

FLOOR_ORDER = ("MZN1", "MZN2", "MZN3", "MZN4", "MZN5", "MZN6")
ELEVATOR_AISLES = {1: 8, 2: 18}
STAIRS = (
    {"id": 1, "aisle1": 5, "aisle2": 6, "cross_aisle": 1},
    {"id": 2, "aisle1": 15, "aisle2": 16, "cross_aisle": 1},
    {"id": 3, "aisle1": 24, "aisle2": 25, "cross_aisle": 1},
    {"id": 4, "aisle1": 9, "aisle2": 10, "cross_aisle": 2},
    {"id": 5, "aisle1": 19, "aisle2": 20, "cross_aisle": 2},
    {"id": 6, "aisle1": 4, "aisle2": 5, "cross_aisle": 3},
    {"id": 7, "aisle1": 14, "aisle2": 15, "cross_aisle": 3},
    {"id": 8, "aisle1": 23, "aisle2": 24, "cross_aisle": 3},
)

DEPOT_ID = "__DEPOT__"


class DataValidationError(ValueError):
    """Raised when the CSV data cannot support the exact-demand model."""


# Model.tex - "Kümeler ve İndisler" eşlemesi:
#   i in I  -> DemandRecord.article_code ve instance.demands anahtarları
#   j in J  -> StockRecord (floor, aisle, side, column, shelf, thm_id) ile temsil edilen tam lokasyon
#   n in N  -> PhysicalNode (floor, aisle, column) ile temsil edilen fiziksel konum
# Burada j'nin 6-boyutlu hali CSV satırından, n'nin 3-boyutlu hali ise aynı fiziksel noktayı paylaşan
# lokasyonların gruplanmasından oluşturulur.
@dataclass(frozen=True)
class DemandRecord:
    article_code: int
    amount: int


@dataclass(frozen=True)
class StockRecord:
    # j = (j1, j2, j3, j4, j5, j6):
    #   floor     -> j1
    #   aisle     -> j2
    #   side      -> j3
    #   column    -> j4
    #   shelf     -> j5
    #   thm_id    -> j6
    location_id: str
    thm_id: str
    article_code: int
    floor: str
    floor_index: int
    aisle: int
    side: str
    column: int
    shelf: int
    stock: int


@dataclass(frozen=True)
class PhysicalNode:
    # n = (j1, j2, j4): "3 boyutlu fiziksel konum indisi"
    node_id: str
    floor: str
    floor_index: int
    aisle: int
    column: int


@dataclass(frozen=True)
class ModelConfig:
    # Model.tex - "Parametreler":
    #   w1, w2, w3 -> objective weights
    # Aşağıdaki iki ayar Model.tex'te açıkça yoktur; bunlar uygulama/pratik amaçlıdır:
    #   cross_floor_penalty_per_floor -> katlar arası geçişe ek ceza
    #   max_route_arcs                -> aşırı büyük MTZ grafikleri için güvenlik sınırı
    distance_weight: float = 1.0
    thm_weight: float = 15.0
    floor_weight: float = 30.0
    cross_floor_penalty_per_floor: float = 0.0
    quantity_integral: bool = True
    enforce_positive_pick_if_opened: bool = True
    max_route_arcs: int | None = 250_000
    model_name: str = "warehouse_picking"


@dataclass
class InstanceData:
    # Model.tex veri objeleri:
    #   t_i      -> demands
    #   s_ij     -> stock_records[*].stock
    #   d_{n,m}  -> distances
    #   J(i)     -> locations_by_article[i]
    #   J(n)     -> locations_by_node[n]
    #   N(j1)    -> nodes_by_floor[j1]
    demands: dict[int, int]
    demand_records: list[DemandRecord]
    stock_records: list[StockRecord]
    physical_nodes: dict[str, PhysicalNode]
    location_to_node: dict[str, str]
    locations_by_article: dict[int, list[str]]
    locations_by_node: dict[str, list[str]]
    locations_by_thm: dict[str, list[str]]
    nodes_by_floor: dict[str, list[str]]
    distances: dict[tuple[str, str], float]


@dataclass
class ModelArtifacts:
    model: Any
    instance: InstanceData
    x: dict[str, Any]
    y: dict[str, Any]
    u: dict[str, Any]
    v: dict[tuple[str, str], Any]
    p: dict[str, Any]
    z: dict[str, Any]
    b: dict[str, Any]


def _require_gurobi() -> None:
    if gp is None or GRB is None:
        raise ImportError(
            "gurobipy is not installed. Install Gurobi's Python package before "
            "building the optimization model."
        )


def _safe_int(value: Any) -> int | None:
    try:
        text = str(value).strip()
    except Exception:
        return None
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _normalize_floor(value: Any) -> str | None:
    if value is None:
        return None
    floor = str(value).strip().upper()
    return floor if floor in FLOOR_ORDER else None


def _normalize_side(value: Any) -> str | None:
    if value is None:
        return None
    side = str(value).strip().upper()
    if side.startswith("L"):
        return "L"
    if side.startswith("R"):
        return "R"
    return None


def _floor_index(floor: str) -> int:
    return FLOOR_ORDER.index(floor) + 1


def get_reversed_aisle_index(aisle: int) -> int:
    return TOTAL_AISLES - aisle + 1


def get_x_coordinate(aisle: int) -> float:
    aisle_1_center = SHELF_DEPTH + (AISLE_WIDTH / 2.0)
    reversed_aisle = get_reversed_aisle_index(aisle)
    return aisle_1_center + ((reversed_aisle - 1) * AISLE_PITCH)


def get_y_coordinate(column: int) -> float:
    if column <= 10:
        return CROSS_AISLE_WIDTH + ((column - 0.5) * COLUMN_LENGTH)
    second_half_column = column - 10
    return (
        CROSS_AISLE_WIDTH
        + (10 * COLUMN_LENGTH)
        + CROSS_AISLE_WIDTH
        + ((second_half_column - 0.5) * COLUMN_LENGTH)
    )


def same_floor_distance(node_a: PhysicalNode, node_b: PhysicalNode) -> float:
    # Model.tex parametresi:
    #   d_{n,m}: "n konumu ile m konumu arasındaki Manhattan mesafesi"
    # Aynı kat içindeki mesafe, Simulation klasöründeki koridor/cross-aisle geometrisiyle
    # uyumlu Manhattan yürüyüş mesafesi olarak hesaplanır.
    x1 = get_x_coordinate(node_a.aisle)
    x2 = get_x_coordinate(node_b.aisle)
    y1 = get_y_coordinate(node_a.column)
    y2 = get_y_coordinate(node_b.column)

    if node_a.aisle == node_b.aisle:
        return abs(y1 - y2)

    return min(abs(y1 - cross_y) + abs(x1 - x2) + abs(cross_y - y2) for cross_y in CROSS_AISLE_CENTERS)


def get_stair_position(stair_id: int) -> tuple[float, float]:
    stair = next(stair for stair in STAIRS if stair["id"] == stair_id)
    x1 = get_x_coordinate(stair["aisle1"])
    x2 = get_x_coordinate(stair["aisle2"])
    x = (x1 + x2) / 2.0

    if stair["cross_aisle"] == 1:
        y = CROSS_AISLE_WIDTH
    elif stair["cross_aisle"] == 2:
        y = CROSS_AISLE_WIDTH + (10 * COLUMN_LENGTH)
    else:
        y = CROSS_AISLE_WIDTH + (10 * COLUMN_LENGTH) + CROSS_AISLE_WIDTH + (10 * COLUMN_LENGTH)

    return x, y


def get_nearest_elevator(aisle: int) -> int:
    dist_to_1 = abs(aisle - ELEVATOR_AISLES[1])
    dist_to_2 = abs(aisle - ELEVATOR_AISLES[2])
    return 1 if dist_to_1 <= dist_to_2 else 2


def get_nearest_stair_to_elevator(elevator_num: int) -> int:
    elevator_x = get_x_coordinate(ELEVATOR_AISLES[elevator_num])
    best_stair_id = 1
    best_distance = math.inf

    for stair in STAIRS:
        if stair["cross_aisle"] != 1:
            continue
        stair_x, _ = get_stair_position(stair["id"])
        horizontal_distance = abs(stair_x - elevator_x)
        if horizontal_distance < best_distance:
            best_distance = horizontal_distance
            best_stair_id = stair["id"]

    return best_stair_id


def get_stair_to_elevator_distance(stair_id: int, elevator_num: int) -> float:
    stair_x, _ = get_stair_position(stair_id)
    elevator_x = get_x_coordinate(ELEVATOR_AISLES[elevator_num])
    horizontal_distance = abs(stair_x - elevator_x)
    return horizontal_distance + CROSS_AISLE_WIDTH


def get_elevator_to_pick_distance(elevator_aisle: int, target_aisle: int, target_column: int) -> float:
    horizontal_distance = abs(target_aisle - elevator_aisle) * AISLE_PITCH
    if target_column <= 10:
        vertical_distance = CROSS_AISLE_WIDTH + ((target_column - 0.5) * COLUMN_LENGTH)
    else:
        vertical_distance = (
            CROSS_AISLE_WIDTH
            + (10 * COLUMN_LENGTH)
            + CROSS_AISLE_WIDTH
            + ((target_column - 10 - 0.5) * COLUMN_LENGTH)
        )
    return horizontal_distance + vertical_distance


def get_entry_exit_distance(node: PhysicalNode) -> float:
    # Model.tex'te katlar arası erişim ayrıntısı verilmediği için, Simulation geometrisine göre
    # fiziksel konuma giriş/çıkış maliyeti hesaplanır. Bu değer, kat değiştiren hareketlerde
    # d_{n,m} parametresini pratikte üretmek için kullanılır.
    elevator_num = get_nearest_elevator(node.aisle)
    stair_id = get_nearest_stair_to_elevator(elevator_num)
    return get_stair_to_elevator_distance(stair_id, elevator_num) + get_elevator_to_pick_distance(
        ELEVATOR_AISLES[elevator_num],
        node.aisle,
        node.column,
    )


def get_distance(node_a: PhysicalNode, node_b: PhysicalNode, config: ModelConfig) -> float:
    # d_{n,m} üretimi:
    #   - aynı kat ise doğrudan Manhattan mesafesi
    #   - farklı kat ise giriş/çıkış maliyeti + isteğe bağlı kat cezası
    # Model.tex'teki amaç fonksiyonu ilk terimi bu değerleri kullanır.
    if node_a.floor == node_b.floor:
        return same_floor_distance(node_a, node_b)

    floor_penalty = config.cross_floor_penalty_per_floor * abs(node_a.floor_index - node_b.floor_index)
    return get_entry_exit_distance(node_a) + get_entry_exit_distance(node_b) + floor_penalty


def load_demands(csv_path: str | Path) -> list[DemandRecord]:
    # PickOrder.csv -> t_i
    # Model.tex:
    #   t_i: "i ürününden toplanması gereken toplam miktar"
    path = Path(csv_path)
    demand_totals: dict[int, int] = defaultdict(int)

    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            article_code = _safe_int(row.get("ARTICLE_CODE"))
            amount = _safe_int(row.get("AMOUNT"))
            if article_code is None or amount is None:
                continue
            if amount < 0:
                raise DataValidationError(f"Negative demand detected for article {article_code}.")
            demand_totals[article_code] += amount

    return [DemandRecord(article_code=article, amount=amount) for article, amount in sorted(demand_totals.items())]


def load_stock(csv_path: str | Path) -> list[StockRecord]:
    # StockData.csv -> s_ij
    # Model.tex:
    #   s_ij: "i ürününün j lokasyonundaki mevcut stok miktarı"
    path = Path(csv_path)
    aggregated: dict[tuple[Any, ...], int] = defaultdict(int)

    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            article_code = _safe_int(row.get("ARTICLE_CODE"))
            aisle = _safe_int(row.get("AISLE"))
            column = _safe_int(row.get("COLUMN"))
            shelf = _safe_int(row.get("SHELF"))
            stock = _safe_int(row.get("STOCK"))
            floor = _normalize_floor(row.get("FLOOR"))
            # Accept both the original sample header and the renamed variant.
            side = _normalize_side(row.get("RIGHT_OR_LEFT") or row.get("LEFT_OR_RIGHT"))
            thm_id = str(row.get("THM_ID", "")).strip()

            if None in (article_code, aisle, column, shelf, stock) or floor is None or side is None or not thm_id:
                continue
            if stock <= 0:
                continue

            if not (1 <= aisle <= TOTAL_AISLES):
                raise DataValidationError(f"Invalid aisle {aisle} for article {article_code}.")
            if not (1 <= column <= TOTAL_COLUMNS):
                raise DataValidationError(f"Invalid column {column} for article {article_code}.")
            if shelf <= 0:
                raise DataValidationError(f"Invalid shelf {shelf} for article {article_code}.")

            key = (thm_id, article_code, floor, aisle, side, column, shelf)
            aggregated[key] += stock

    records: list[StockRecord] = []
    sorted_items = sorted(
        aggregated.items(),
        key=lambda item: (item[0][2], item[0][3], item[0][5], item[0][4], item[0][6], item[0][0], item[0][1]),
    )

    for index, (key, stock) in enumerate(sorted_items, start=1):
        thm_id, article_code, floor, aisle, side, column, shelf = key
        records.append(
            StockRecord(
                location_id=f"j{index:05d}",
                thm_id=thm_id,
                article_code=article_code,
                floor=floor,
                floor_index=_floor_index(floor),
                aisle=aisle,
                side=side,
                column=column,
                shelf=shelf,
                stock=stock,
            )
        )

    return records


def _filter_demands(
    demand_records: Sequence[DemandRecord],
    articles: Iterable[int] | None,
) -> list[DemandRecord]:
    if articles is None:
        return list(demand_records)
    article_set = {int(article) for article in articles}
    return [record for record in demand_records if record.article_code in article_set]


def _filter_stock(
    stock_records: Sequence[StockRecord],
    floors: Iterable[str] | None,
    articles: Iterable[int] | None,
) -> list[StockRecord]:
    floor_set = {str(floor).upper() for floor in floors} if floors is not None else None
    article_set = {int(article) for article in articles} if articles is not None else None

    filtered = []
    for record in stock_records:
        if floor_set is not None and record.floor not in floor_set:
            continue
        if article_set is not None and record.article_code not in article_set:
            continue
        filtered.append(record)
    return filtered


def suggest_test_articles(
    demand_records: Sequence[DemandRecord],
    stock_records: Sequence[StockRecord],
    floor: str,
    max_articles: int = 5,
) -> list[int]:
    # Bu yardımcı fonksiyon Model.tex'in bir parçası değildir.
    # Amacı, bir sonraki test adımı olan "tek kat + az ürün" senaryosu için
    # fizibil ve küçük bir alt örnek önermektir.
    floor = floor.upper()
    demands = {record.article_code: record.amount for record in demand_records}
    available_on_floor: dict[int, int] = defaultdict(int)
    node_count_on_floor: dict[int, set[tuple[int, int]]] = defaultdict(set)
    thm_count_on_floor: dict[int, set[str]] = defaultdict(set)

    for record in stock_records:
        if record.floor != floor:
            continue
        available_on_floor[record.article_code] += record.stock
        node_count_on_floor[record.article_code].add((record.aisle, record.column))
        thm_count_on_floor[record.article_code].add(record.thm_id)

    candidates: list[tuple[int, int, int, int]] = []
    for article_code, demand in demands.items():
        if available_on_floor[article_code] < demand:
            continue
        candidates.append(
            (
                len(node_count_on_floor[article_code]),
                len(thm_count_on_floor[article_code]),
                demand,
                article_code,
            )
        )

    candidates.sort()
    return [article_code for _, _, _, article_code in candidates[:max_articles]]


def build_instance(
    demand_csv: str | Path,
    stock_csv: str | Path,
    *,
    floors: Iterable[str] | None = None,
    articles: Iterable[int] | None = None,
    config: ModelConfig | None = None,
) -> InstanceData:
    """Build the indexed sets and parameters used by the mathematical model.

    Model.tex ile birebir eşleme:
      - I       -> demand_records / demands
      - J       -> stock_records
      - N       -> physical_nodes
      - t_i     -> demands
      - s_ij    -> stock_records[*].stock
      - d_{n,m} -> distances
    """
    config = config or ModelConfig()
    demand_records = _filter_demands(load_demands(demand_csv), articles)
    stock_records = _filter_stock(load_stock(stock_csv), floors, articles)

    if not demand_records:
        raise DataValidationError("No demand rows remain after filtering.")
    if not stock_records:
        raise DataValidationError("No stock rows remain after filtering.")

    demands = {record.article_code: record.amount for record in demand_records}
    available_by_article: dict[int, int] = defaultdict(int)
    for record in stock_records:
        available_by_article[record.article_code] += record.stock

    missing = sorted(article for article in demands if available_by_article[article] == 0)
    insufficient = sorted(
        (article, demands[article], available_by_article[article])
        for article in demands
        if 0 < available_by_article[article] < demands[article]
    )
    if missing or insufficient:
        message_parts = []
        if missing:
            sample = ", ".join(str(article) for article in missing[:15])
            more = "" if len(missing) <= 15 else f", ... (+{len(missing) - 15} more)"
            message_parts.append(f"missing stock for articles [{sample}{more}]")
        if insufficient:
            sample = ", ".join(f"{article} (need {need}, have {have})" for article, need, have in insufficient[:10])
            more = "" if len(insufficient) <= 10 else f", ... (+{len(insufficient) - 10} more)"
            message_parts.append(f"insufficient stock for [{sample}{more}]")
        raise DataValidationError("Cannot build an exact-demand instance: " + "; ".join(message_parts) + ".")

    stock_records = [record for record in stock_records if record.article_code in demands]

    # J kümesinden N kümesine geçiş:
    # Model.tex'te j tam lokasyon, n ise fiziksel konumdur.
    # Aynı (floor, aisle, column) paylaşan farklı shelf/side/THM kombinasyonları
    # aynı fiziksel ziyaret noktası n altında toplanır.
    physical_nodes: dict[tuple[str, int, int], PhysicalNode] = {}
    location_to_node: dict[str, str] = {}
    locations_by_article: dict[int, list[str]] = defaultdict(list)
    locations_by_node: dict[str, list[str]] = defaultdict(list)
    locations_by_thm: dict[str, list[str]] = defaultdict(list)
    nodes_by_floor: dict[str, list[str]] = defaultdict(list)

    node_keys = sorted({(record.floor, record.aisle, record.column) for record in stock_records}, key=lambda key: (_floor_index(key[0]), key[1], key[2]))
    for index, key in enumerate(node_keys, start=1):
        floor, aisle, column = key
        node = PhysicalNode(
            node_id=f"n{index:05d}",
            floor=floor,
            floor_index=_floor_index(floor),
            aisle=aisle,
            column=column,
        )
        physical_nodes[key] = node
        nodes_by_floor[floor].append(node.node_id)

    node_lookup = physical_node_lookup(physical_nodes)
    for floor in nodes_by_floor:
        nodes_by_floor[floor].sort(key=lambda node_id: (node_lookup[node_id].aisle, node_lookup[node_id].column))

    for record in stock_records:
        node_id = physical_nodes[(record.floor, record.aisle, record.column)].node_id
        location_to_node[record.location_id] = node_id
        locations_by_article[record.article_code].append(record.location_id)
        locations_by_node[node_id].append(record.location_id)
        locations_by_thm[record.thm_id].append(record.location_id)

    # d_{n,m} parametresi bütün fiziksel düğüm çiftleri için önceden hesaplanır.
    distances: dict[tuple[str, str], float] = {}
    node_ids = sorted(node_lookup)
    for node_id in node_ids:
        node = node_lookup[node_id]
        entry_distance = get_entry_exit_distance(node)
        distances[(DEPOT_ID, node_id)] = entry_distance
        distances[(node_id, DEPOT_ID)] = entry_distance

    for origin_id in node_ids:
        origin = node_lookup[origin_id]
        for destination_id in node_ids:
            if origin_id == destination_id:
                continue
            destination = node_lookup[destination_id]
            distances[(origin_id, destination_id)] = get_distance(origin, destination, config)

    return InstanceData(
        demands=demands,
        demand_records=demand_records,
        stock_records=stock_records,
        physical_nodes=node_lookup,
        location_to_node=location_to_node,
        locations_by_article=dict(locations_by_article),
        locations_by_node=dict(locations_by_node),
        locations_by_thm=dict(locations_by_thm),
        nodes_by_floor=dict(nodes_by_floor),
        distances=distances,
    )


def physical_node_lookup(physical_nodes: Mapping[tuple[str, int, int], PhysicalNode]) -> dict[str, PhysicalNode]:
    return {node.node_id: node for node in physical_nodes.values()}


def build_gurobi_model(instance: InstanceData, config: ModelConfig | None = None) -> ModelArtifacts:
    """Create the Gurobi model with comments aligned to Model.tex.

    Karar değişkenleri:
      - x_ij in {0,1}: "i ürününün j lokasyonundan toplanıp toplanmama durumu"
      - y_ij >= 0    : "i ürününün j lokasyonundan toplanan miktarı"
      - u_n in {0,1} : "n konumunun ziyaret edilip edilmeme durumu"
      - v_{n,m}      : "n konumundan m konumuna doğrudan gidilme durumu"
      - p_n          : "n konumunun tur içindeki ziyaret sırası (MTZ kısıtı için)"
      - z_{j1}       : "j1 numaralı kata girilip girilmediği durumu"
      - b_{j6}       : "j6 numaralı THM kutusunun açılıp açılmadığı durumu"
    """
    _require_gurobi()
    config = config or ModelConfig()

    model = gp.Model(config.model_name)

    stock_ids = [record.location_id for record in instance.stock_records]
    node_ids = sorted(instance.physical_nodes)
    floor_ids = sorted(instance.nodes_by_floor, key=_floor_index)
    thm_ids = sorted(instance.locations_by_thm)
    augmented_nodes = [DEPOT_ID, *node_ids]

    quantity_vtype = GRB.INTEGER if config.quantity_integral else GRB.CONTINUOUS

    # Model.tex - "Karar Değişkenleri"
    x = model.addVars(stock_ids, vtype=GRB.BINARY, name="x")
    y = model.addVars(stock_ids, lb=0.0, vtype=quantity_vtype, name="y")
    u = model.addVars(node_ids, vtype=GRB.BINARY, name="u")
    z = model.addVars(floor_ids, vtype=GRB.BINARY, name="z")
    b = model.addVars(thm_ids, vtype=GRB.BINARY, name="b")
    p = model.addVars(node_ids, lb=0.0, ub=len(node_ids), vtype=GRB.CONTINUOUS, name="p")

    # Uygulama detayı:
    # Model.tex'teki v_{n,m} değişkenleri fiziksel düğümler arasında tanımlı.
    # Kodda MTZ turunu başlatıp bitirmek için buna ek olarak sanal bir depot kullanılır.
    arc_index = [(origin, destination) for origin in augmented_nodes for destination in augmented_nodes if origin != destination]
    if config.max_route_arcs is not None and len(arc_index) > config.max_route_arcs:
        raise DataValidationError(
            "The filtered instance still creates "
            f"{len(arc_index):,} routing arcs, which is too large for the default MTZ build. "
            "Filter to fewer floors/articles or raise ModelConfig.max_route_arcs explicitly."
        )
    v = model.addVars(arc_index, vtype=GRB.BINARY, name="v")

    # Model.tex - "Amaç Fonksiyonu"
    #   min Z = w1 * sum_{n,m} d_{n,m} v_{n,m}
    #         + w2 * sum_{j6} b_{j6}
    #         + w3 * sum_{j1} z_{j1}
    #
    # Terim 1: "Toplam yürünen Manhattan mesafesi."
    # Terim 2: "Toplam kullanılan (açılan) THM kutusu sayısı."
    # Terim 3: "Toplam girilen (aktifleşen) kat sayısı."
    model.setObjective(
        config.distance_weight * gp.quicksum(instance.distances[arc] * v[arc] for arc in arc_index)
        + config.thm_weight * gp.quicksum(b[thm_id] for thm_id in thm_ids)
        + config.floor_weight * gp.quicksum(z[floor_id] for floor_id in floor_ids),
        GRB.MINIMIZE,
    )

    for record in instance.stock_records:
        # (cons:stok)
        # "Bir lokasyondan toplanan ürün miktarı, o lokasyondaki stok miktarını geçemez."
        model.addConstr(
            y[record.location_id] <= record.stock * x[record.location_id],
            name=f"stock_cap_{record.location_id}",
        )

        # Uygulama sıkılaştırması - Model.tex'te yok:
        # Eğer x_ij = 1 ise, integral miktar modelinde y_ij en az 1 olsun.
        # Bu, "açılmış ama sıfır alınmış" lokasyonları engeller.
        if config.enforce_positive_pick_if_opened and config.quantity_integral:
            model.addConstr(
                y[record.location_id] >= x[record.location_id],
                name=f"stock_open_lb_{record.location_id}",
            )

        # (cons:thm)
        # "Eğer bir lokasyondan ürün toplandıysa, ilgili THM kutusu açılmış sayılır."
        model.addConstr(
            x[record.location_id] <= b[record.thm_id],
            name=f"thm_link_{record.location_id}",
        )

        # (cons:ziyaret)
        # "Ürün toplama yapılan her lokasyonun bulunduğu fiziksel konuma uğranmış olmalıdır."
        model.addConstr(
            x[record.location_id] <= u[instance.location_to_node[record.location_id]],
            name=f"visit_link_{record.location_id}",
        )

    for article_code, location_ids in sorted(instance.locations_by_article.items()):
        # (cons:talep)
        # "Her ürün için toplanması gereken toplam miktar sağlanmalıdır."
        model.addConstr(
            gp.quicksum(y[location_id] for location_id in location_ids) == instance.demands[article_code],
            name=f"demand_{article_code}",
        )

    for node_id, location_ids in sorted(instance.locations_by_node.items()):
        # Uygulama tamamlayıcı bağı:
        # Model.tex x_ij <= u_n yönünü verir. Burada ters yön de eklenir:
        # bir fiziksel nokta ziyaret edilmişse, o düğümde en az bir lokasyon açılmış olmalıdır.
        model.addConstr(
            u[node_id] <= gp.quicksum(x[location_id] for location_id in location_ids),
            name=f"visit_reverse_link_{node_id}",
        )

    for floor_id, floor_node_ids in sorted(instance.nodes_by_floor.items(), key=lambda item: _floor_index(item[0])):
        for node_id in floor_node_ids:
            # (cons:kat)
            # "Eğer bir konuma gidildiyse, o konumun bulunduğu kat ziyaret edilmiş sayılır."
            model.addConstr(
                u[node_id] <= z[floor_id],
                name=f"floor_link_{floor_id}_{node_id}",
            )

        # Uygulama tamamlayıcı bağı:
        # z_j1 değişkeni 1 ise, ilgili katta gerçekten en az bir ziyaret olsun.
        model.addConstr(
            z[floor_id] <= gp.quicksum(u[node_id] for node_id in floor_node_ids),
            name=f"floor_reverse_link_{floor_id}",
        )

    for thm_id, location_ids in sorted(instance.locations_by_thm.items()):
        # Uygulama tamamlayıcı bağı:
        # b_j6 değişkeni 1 ise, o THM altında gerçekten en az bir açık lokasyon olsun.
        model.addConstr(
            b[thm_id] <= gp.quicksum(x[location_id] for location_id in location_ids),
            name=f"thm_reverse_link_{thm_id}",
        )

    for node_id in node_ids:
        outgoing = [destination for destination in augmented_nodes if destination != node_id]
        incoming = [origin for origin in augmented_nodes if origin != node_id]

        # (cons:flow1)
        # "Akış korunumu kısıtları. Bir noktaya girildiyse oradan çıkılmalıdır."
        model.addConstr(
            gp.quicksum(v[node_id, destination] for destination in outgoing) == u[node_id],
            name=f"flow_out_{node_id}",
        )

        # (cons:flow2)
        # "Akış korunumu kısıtları. Bir noktaya girildiyse oradan çıkılmalıdır."
        model.addConstr(
            gp.quicksum(v[origin, node_id] for origin in incoming) == u[node_id],
            name=f"flow_in_{node_id}",
        )

    # Uygulama detayı - Model.tex'te yok:
    # Sanal depot'tan tam bir tur oluşturmak için bir çıkış ve bir dönüş yayı zorunlu kılınır.
    model.addConstr(
        gp.quicksum(v[DEPOT_ID, node_id] for node_id in node_ids) == 1,
        name="depot_out",
    )
    model.addConstr(
        gp.quicksum(v[node_id, DEPOT_ID] for node_id in node_ids) == 1,
        name="depot_in",
    )

    mtz_big_m = len(node_ids)
    for node_id in node_ids:
        # MTZ için p_n ancak düğüm ziyaret edilirse aktifleşsin.
        model.addConstr(p[node_id] >= u[node_id], name=f"mtz_lb_{node_id}")
        model.addConstr(p[node_id] <= mtz_big_m * u[node_id], name=f"mtz_ub_{node_id}")

    for origin in node_ids:
        for destination in node_ids:
            if origin == destination:
                continue
            # (cons:mtz)
            # "Miller-Tucker-Zemlin (MTZ) alt tur eleme kısıtı. Rotaların tek bir kapalı
            # döngü olmasını ve alt turların oluşmamasını sağlar."
            model.addConstr(
                p[origin] - p[destination] + (mtz_big_m * v[origin, destination]) <= mtz_big_m - 1,
                name=f"mtz_{origin}_{destination}",
            )

    model.update()
    return ModelArtifacts(model=model, instance=instance, x=x, y=y, u=u, v=v, p=p, z=z, b=b)


def build_model_from_csv(
    demand_csv: str | Path,
    stock_csv: str | Path,
    *,
    floors: Iterable[str] | None = None,
    articles: Iterable[int] | None = None,
    config: ModelConfig | None = None,
) -> ModelArtifacts:
    config = config or ModelConfig()
    instance = build_instance(demand_csv, stock_csv, floors=floors, articles=articles, config=config)
    return build_gurobi_model(instance, config=config)


def extract_solution(artifacts: ModelArtifacts, tolerance: float = 1e-6) -> dict[str, Any]:
    model = artifacts.model
    if model.SolCount == 0:
        raise RuntimeError("Model does not currently contain a feasible solution.")

    picked_locations = []
    for record in artifacts.instance.stock_records:
        quantity = artifacts.y[record.location_id].X
        if quantity <= tolerance:
            continue
        picked_locations.append(
            {
                "location_id": record.location_id,
                "thm_id": record.thm_id,
                "article_code": record.article_code,
                "floor": record.floor,
                "aisle": record.aisle,
                "column": record.column,
                "shelf": record.shelf,
                "side": record.side,
                "picked_quantity": quantity,
            }
        )

    active_arcs = [arc for arc, var in artifacts.v.items() if var.X > 0.5]
    active_nodes = [node_id for node_id, var in artifacts.u.items() if var.X > 0.5]
    active_floors = [floor_id for floor_id, var in artifacts.z.items() if var.X > 0.5]
    active_thms = [thm_id for thm_id, var in artifacts.b.items() if var.X > 0.5]
    route_nodes = _ordered_route_nodes(active_arcs, active_nodes)

    return {
        "objective_value": model.ObjVal,
        "picked_locations": picked_locations,
        "active_nodes": active_nodes,
        "active_arcs": active_arcs,
        "route_nodes": route_nodes,
        "active_floors": active_floors,
        "active_thms": active_thms,
    }


def _ordered_route_nodes(
    active_arcs: Sequence[tuple[str, str]],
    active_nodes: Sequence[str],
) -> list[str]:
    """Reconstruct the visited-node order from the solved MTZ arc variables.

    The optimization model stores routing decisions as binary arc variables
    v_(n,m). For the pick CSV we need a human-readable stop order, so this
    helper follows the unique successor chain starting from the virtual depot
    and returns the physical nodes in visit order.

    If a partially recovered route ever leaves some active nodes untraversed
    because of numerical tolerance or an unexpected incumbent shape, those
    missing nodes are appended deterministically as a safe fallback so export
    still succeeds.
    """
    successors = {origin: destination for origin, destination in active_arcs}

    ordered_nodes: list[str] = []
    seen_nodes: set[str] = set()
    current = successors.get(DEPOT_ID)

    while current is not None and current != DEPOT_ID and current not in seen_nodes:
        ordered_nodes.append(current)
        seen_nodes.add(current)
        current = successors.get(current)

    for node_id in sorted(active_nodes):
        if node_id not in seen_nodes:
            ordered_nodes.append(node_id)

    return ordered_nodes


def _format_pick_amount(quantity: float, tolerance: float = 1e-6) -> int | str:
    rounded_quantity = round(quantity)
    if math.isclose(quantity, rounded_quantity, abs_tol=tolerance):
        return int(rounded_quantity)
    return f"{quantity:.6f}".rstrip("0").rstrip(".")


def build_pick_data_rows(artifacts: ModelArtifacts, tolerance: float = 1e-6) -> list[dict[str, Any]]:
    """Create rows in the PickDataSample.csv shape plus PICK_ORDER.

    PICK_ORDER is interpreted as the stop order of the physical visit point.
    If multiple picked article lines belong to the same physical node, they
    intentionally share the same PICK_ORDER because the picker reaches that
    node once and may collect several items there.
    """
    solution = extract_solution(artifacts, tolerance=tolerance)
    route_position = {node_id: index + 1 for index, node_id in enumerate(solution["route_nodes"])}

    rows: list[dict[str, Any]] = []
    for pick in solution["picked_locations"]:
        floor = pick["floor"]
        node_id = artifacts.instance.location_to_node[pick["location_id"]]
        rows.append(
            {
                "PICKER_ID": f"PICKER_{floor}",
                "THM_ID": pick["thm_id"],
                "ARTICLE_CODE": pick["article_code"],
                "FLOOR": floor,
                "AISLE": pick["aisle"],
                "COLUMN": pick["column"],
                "SHELF": pick["shelf"],
                "LEFT_OR_RIGHT": pick["side"],
                "AMOUNT": _format_pick_amount(pick["picked_quantity"], tolerance=tolerance),
                "PICKCAR_ID": f"PICKCAR_{floor}",
                "PICK_ORDER": route_position[node_id],
            }
        )

    rows.sort(
        key=lambda row: (
            row["PICK_ORDER"],
            _floor_index(str(row["FLOOR"])),
            int(row["AISLE"]),
            int(row["COLUMN"]),
            int(row["SHELF"]),
            str(row["LEFT_OR_RIGHT"]),
            str(row["THM_ID"]),
            int(row["ARTICLE_CODE"]),
        )
    )
    return rows


def write_pick_data_csv(
    artifacts: ModelArtifacts,
    csv_path: str | Path,
    tolerance: float = 1e-6,
) -> Path:
    """Write the solved picking plan as a flat CSV for downstream execution."""
    output_path = Path(csv_path)
    rows = build_pick_data_rows(artifacts, tolerance=tolerance)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "PICKER_ID",
        "THM_ID",
        "ARTICLE_CODE",
        "FLOOR",
        "AISLE",
        "COLUMN",
        "SHELF",
        "LEFT_OR_RIGHT",
        "AMOUNT",
        "PICKCAR_ID",
        "PICK_ORDER",
    ]

    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def build_alternative_location_rows(
    artifacts: ModelArtifacts,
    tolerance: float = 1e-6,
) -> list[dict[str, Any]]:
    """Create a debug-friendly CSV view of all candidate locations.

    This export is intentionally wider than PickDataSample.csv because its
    purpose is validation, not downstream execution. Each row corresponds to
    one feasible stock location j for an ordered article i in the solved
    instance, and the flags show whether that location/THM/node was actually
    used by the optimizer.
    """
    solution = extract_solution(artifacts, tolerance=tolerance)
    picked_quantity_by_location = {
        pick["location_id"]: pick["picked_quantity"] for pick in solution["picked_locations"]
    }
    active_nodes = set(solution["active_nodes"])
    active_thms = set(solution["active_thms"])
    route_position = {node_id: index + 1 for index, node_id in enumerate(solution["route_nodes"])}

    rows: list[dict[str, Any]] = []
    for record in artifacts.instance.stock_records:
        node_id = artifacts.instance.location_to_node[record.location_id]
        picked_quantity = picked_quantity_by_location.get(record.location_id, 0.0)
        is_selected = picked_quantity > tolerance

        rows.append(
            {
                "ARTICLE_CODE": record.article_code,
                "ARTICLE_DEMAND": artifacts.instance.demands[record.article_code],
                "LOCATION_ID": record.location_id,
                "THM_ID": record.thm_id,
                "FLOOR": record.floor,
                "AISLE": record.aisle,
                "COLUMN": record.column,
                "SHELF": record.shelf,
                "LEFT_OR_RIGHT": record.side,
                "AVAILABLE_STOCK": record.stock,
                "NODE_ID": node_id,
                "NODE_VISITED": 1 if node_id in active_nodes else 0,
                "THM_OPENED": 1 if record.thm_id in active_thms else 0,
                "IS_SELECTED": 1 if is_selected else 0,
                "PICKED_AMOUNT": _format_pick_amount(picked_quantity, tolerance=tolerance) if is_selected else 0,
                "PICK_ORDER": route_position.get(node_id, ""),
            }
        )

    rows.sort(
        key=lambda row: (
            int(row["ARTICLE_CODE"]),
            -int(row["IS_SELECTED"]),
            int(row["PICK_ORDER"]) if str(row["PICK_ORDER"]).strip() else 10**9,
            _floor_index(str(row["FLOOR"])),
            int(row["AISLE"]),
            int(row["COLUMN"]),
            int(row["SHELF"]),
            str(row["LEFT_OR_RIGHT"]),
            str(row["THM_ID"]),
            str(row["LOCATION_ID"]),
        )
    )
    return rows


def write_alternative_locations_csv(
    artifacts: ModelArtifacts,
    csv_path: str | Path,
    tolerance: float = 1e-6,
) -> Path:
    """Write all feasible candidate locations for the solved instance."""
    output_path = Path(csv_path)
    rows = build_alternative_location_rows(artifacts, tolerance=tolerance)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "ARTICLE_CODE",
        "ARTICLE_DEMAND",
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

    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def _parse_article_list(value: str | None) -> list[int] | None:
    if value is None or not value.strip():
        return None
    return [int(token.strip()) for token in value.split(",") if token.strip()]


def _parse_floor_list(value: str | None) -> list[str] | None:
    if value is None or not value.strip():
        return None
    return [token.strip().upper() for token in value.split(",") if token.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the warehouse picking Gurobi model.")
    parser.add_argument("--orders", default="PickOrder.csv", help="Path to the pick-order CSV.")
    parser.add_argument("--stock", default="StockData.csv", help="Path to the stock CSV.")
    parser.add_argument("--floors", default=None, help="Comma-separated floor filter, e.g. MZN1 or MZN1,MZN2.")
    parser.add_argument("--articles", default=None, help="Comma-separated article filter, e.g. 258,376,471.")
    parser.add_argument("--suggest-floor-test", default=None, help="Suggest an easy feasible subset for one floor.")
    parser.add_argument("--max-test-items", type=int, default=5, help="Maximum items for --suggest-floor-test.")
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--thm-weight", type=float, default=1.0)
    parser.add_argument("--floor-weight", type=float, default=1.0)
    parser.add_argument("--cross-floor-penalty", type=float, default=0.0)
    parser.add_argument(
        "--max-route-arcs",
        type=int,
        default=250000,
        help="Safety cap for the number of routing arcs in the MTZ layer.",
    )
    parser.add_argument(
        "--write-lp",
        default=None,
        help="Optional .lp output path. The script only builds the model unless --optimize is also used.",
    )
    parser.add_argument(
        "--pick-data-output",
        default="PickDataOutput.csv",
        help=(
            "Output CSV path for the solved pick list in PickDataSample.csv format "
            "plus PICK_ORDER. Written after a feasible --optimize run; pass an empty "
            "string to disable."
        ),
    )
    parser.add_argument(
        "--alternative-locations-output",
        default="AlternativeLocationsOutput.csv",
        help=(
            "Output CSV path listing every feasible candidate location for the solved "
            "instance, with selected/opened/visited flags. Written after a feasible "
            "--optimize run; pass an empty string to disable."
        ),
    )
    parser.add_argument("--optimize", action="store_true", help="Run optimization after building the model.")
    parser.add_argument("--time-limit", type=float, default=None, help="Optional Gurobi time limit in seconds.")
    args = parser.parse_args(argv)

    config = ModelConfig(
        distance_weight=args.distance_weight,
        thm_weight=args.thm_weight,
        floor_weight=args.floor_weight,
        cross_floor_penalty_per_floor=args.cross_floor_penalty,
        max_route_arcs=args.max_route_arcs,
    )

    if args.suggest_floor_test:
        demands = load_demands(args.orders)
        stock = load_stock(args.stock)
        suggested = suggest_test_articles(demands, stock, args.suggest_floor_test, max_articles=args.max_test_items)
        if not suggested:
            raise DataValidationError(f"No feasible single-floor subset found for {args.suggest_floor_test.upper()}.")
        print(",".join(str(article) for article in suggested))
        return 0

    floors = _parse_floor_list(args.floors)
    articles = _parse_article_list(args.articles)
    artifacts = build_model_from_csv(args.orders, args.stock, floors=floors, articles=articles, config=config)

    print(
        "Model built successfully with "
        f"{len(artifacts.instance.demands)} articles, "
        f"{len(artifacts.instance.stock_records)} stock locations, and "
        f"{len(artifacts.instance.physical_nodes)} physical nodes."
    )

    if args.write_lp:
        artifacts.model.write(args.write_lp)
        print(f"LP written to {args.write_lp}")

    if args.time_limit is not None:
        artifacts.model.Params.TimeLimit = args.time_limit

    if args.optimize:
        artifacts.model.optimize()
        if artifacts.model.SolCount > 0:
            solution = extract_solution(artifacts)
            print(f"Objective: {solution['objective_value']:.4f}")
            print(f"Active floors: {', '.join(solution['active_floors'])}")
            print(f"Opened THMs: {len(solution['active_thms'])}")
            print(f"Visited nodes: {len(solution['active_nodes'])}")
            if args.pick_data_output:
                output_path = write_pick_data_csv(artifacts, args.pick_data_output)
                print(f"Pick data written to {output_path}")
            if args.alternative_locations_output:
                alternative_output_path = write_alternative_locations_csv(
                    artifacts,
                    args.alternative_locations_output,
                )
                print(f"Alternative locations written to {alternative_output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

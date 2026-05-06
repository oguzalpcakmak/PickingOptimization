#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

constexpr double AISLE_WIDTH = 1.36;
constexpr double COLUMN_LENGTH = 2.90;
constexpr double SHELF_DEPTH = 1.16;
constexpr double CROSS_AISLE_WIDTH = 2.70;
constexpr int TOTAL_AISLES = 27;
constexpr int TOTAL_COLUMNS = 20;
constexpr double AISLE_PITCH = AISLE_WIDTH + (2.0 * SHELF_DEPTH);
constexpr double EPS = 1e-9;
const std::vector<std::string> FLOOR_ORDER = {"MZN1", "MZN2", "MZN3", "MZN4", "MZN5", "MZN6"};
const std::vector<double> CROSS_AISLE_CENTERS = {
    CROSS_AISLE_WIDTH / 2.0,
    CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH + (CROSS_AISLE_WIDTH / 2.0),
    CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH +
        (CROSS_AISLE_WIDTH / 2.0),
};

struct Node {
    int aisle = 0;
    int column = 0;
    bool operator<(const Node& other) const {
        return std::tie(aisle, column) < std::tie(other.aisle, other.column);
    }
    bool operator==(const Node& other) const {
        return aisle == other.aisle && column == other.column;
    }
};

struct Loc {
    std::string lid;
    std::string thm_id;
    int article = 0;
    std::string floor;
    int aisle = 0;
    std::string side;
    int column = 0;
    int shelf = 0;
    int stock = 0;

    Node node() const { return Node{aisle, column}; }
};

struct Weights {
    double distance = 1.0;
    double thm = 15.0;
    double floor = 30.0;
};

struct Candidate {
    std::size_t loc_idx = 0;
    int take = 0;
    double unit_cost = 0.0;
    double marginal_cost = 0.0;
    double route_delta = 0.0;
    std::size_t insert_index = 0;
    bool new_floor = false;
    bool new_thm = false;
    bool new_node = false;
    bool has_route_nodes = false;
    std::vector<Node> route_nodes;
    double route_total_cost = 0.0;
};

struct FloorResult {
    std::string floor;
    std::map<std::size_t, int> picks;
    std::vector<Node> route;
    double route_distance = 0.0;
    std::set<std::string> opened_thms;
};

struct Solution {
    std::string algorithm;
    std::vector<FloorResult> floor_results;
    double total_distance = 0.0;
    std::size_t total_thms = 0;
    std::size_t total_floors = 0;
    std::size_t total_picks = 0;
    double solve_time = 0.0;
    double objective = 0.0;
    std::map<std::string, std::string> notes;
};

struct Problem {
    std::map<int, int> demands;
    std::vector<Loc> locs;
    std::map<int, std::vector<std::size_t>> article_to_candidates;
};

struct Args {
    fs::path orders = "data/full/PickOrder.csv";
    fs::path stock = "data/full/StockData.csv";
    double distance_weight = 1.0;
    double thm_weight = 15.0;
    double floor_weight = 30.0;
    double time_limit = 300.0;
    bool fallback_on_time_limit = true;
    double fallback_alpha = 0.25;
    std::size_t fallback_article_rcl_size = 6;
    std::size_t fallback_location_rcl_size = 5;
    std::uint64_t fallback_seed = 7;
    std::string fallback_method = "grasp";
    std::string cleanup_operator = "2-opt";
    std::string cleanup_strategy = "best";
    std::size_t cleanup_passes = 3;
    std::optional<std::set<std::string>> floors;
    std::optional<std::set<int>> articles;
    fs::path output = "outputs/benchmark_outputs/cpp_current_best/current_best_pick.csv";
    fs::path alt_output = "outputs/benchmark_outputs/cpp_current_best/current_best_alt.csv";
    fs::path summary_output = "outputs/benchmark_outputs/cpp_current_best/current_best_summary.json";
};

struct FallbackSummary {
    std::size_t articles = 0;
    std::size_t steps = 0;
    std::size_t candidate_evals = 0;
    std::string rule = "not used";
    std::size_t visited_box_hits = 0;
    std::size_t visited_half_block_hits = 0;
    std::size_t visited_aisle_hits = 0;
    std::size_t visited_floor_hits = 0;
    std::size_t random_hits = 0;
};

struct SimpleRng {
    std::uint64_t state;
    explicit SimpleRng(std::uint64_t seed) : state(seed == 0 ? 0x9e3779b97f4a7c15ULL : seed) {}
    std::uint64_t next_u64() {
        state = state * 6364136223846793005ULL + 1442695040888963407ULL;
        return state;
    }
    std::size_t randrange(std::size_t upper) {
        if (upper <= 1) return 0;
        return static_cast<std::size_t>(next_u64() % upper);
    }
};

static std::string trim(const std::string& value) {
    std::size_t start = 0;
    while (start < value.size() && std::isspace(static_cast<unsigned char>(value[start]))) start++;
    std::size_t end = value.size();
    while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1]))) end--;
    return value.substr(start, end - start);
}

static std::string upper(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::toupper(ch));
    });
    return value;
}

static bool starts_with(const std::string& value, char prefix) {
    return !value.empty() && value.front() == prefix;
}

static std::string csv_escape(const std::string& value) {
    if (value.find_first_of(",\"\n") == std::string::npos) return value;
    std::string escaped = "\"";
    for (char ch : value) {
        if (ch == '"') escaped += "\"\"";
        else escaped += ch;
    }
    escaped += '"';
    return escaped;
}

static std::string json_escape(const std::string& value) {
    std::string escaped = "\"";
    for (char ch : value) {
        switch (ch) {
            case '\\': escaped += "\\\\"; break;
            case '"': escaped += "\\\""; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default: escaped += ch; break;
        }
    }
    escaped += '"';
    return escaped;
}

static std::string fixed6(double value) {
    std::ostringstream out;
    out << std::fixed << std::setprecision(6) << value;
    return out.str();
}

static void ensure_parent(const fs::path& path) {
    if (path.has_parent_path()) fs::create_directories(path.parent_path());
}

static std::vector<std::string> parse_csv_line(const std::string& line, char delimiter = ',') {
    std::vector<std::string> out;
    std::string field;
    bool in_quotes = false;
    for (std::size_t idx = 0; idx < line.size(); ++idx) {
        char ch = line[idx];
        if (ch == '"') {
            if (in_quotes && idx + 1 < line.size() && line[idx + 1] == '"') {
                field += '"';
                ++idx;
            } else {
                in_quotes = !in_quotes;
            }
        } else if (ch == delimiter && !in_quotes) {
            out.push_back(trim(field));
            field.clear();
        } else {
            field += ch;
        }
    }
    out.push_back(trim(field));
    return out;
}

static std::vector<std::map<std::string, std::string>> read_csv(const fs::path& path) {
    std::ifstream file(path);
    if (!file) throw std::runtime_error("failed to read " + path.string());
    std::string header_line;
    if (!std::getline(file, header_line)) throw std::runtime_error(path.string() + " is empty");
    if (header_line.rfind("\xEF\xBB\xBF", 0) == 0) header_line.erase(0, 3);
    if (!header_line.empty() && header_line.back() == '\r') header_line.pop_back();
    auto headers = parse_csv_line(header_line);
    std::vector<std::map<std::string, std::string>> rows;
    std::string line;
    while (std::getline(file, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (trim(line).empty()) continue;
        auto values = parse_csv_line(line);
        std::map<std::string, std::string> row;
        for (std::size_t idx = 0; idx < headers.size(); ++idx) {
            row[headers[idx]] = idx < values.size() ? values[idx] : "";
        }
        rows.push_back(std::move(row));
    }
    return rows;
}

static std::optional<int> parse_i32(const std::string& raw) {
    std::string text = trim(raw);
    if (text.empty()) return std::nullopt;
    try {
        std::size_t pos = 0;
        int value = std::stoi(text, &pos);
        if (pos == text.size()) return value;
    } catch (...) {
    }
    try {
        return static_cast<int>(std::stod(text));
    } catch (...) {
        return std::nullopt;
    }
}

static std::optional<std::string> norm_floor(const std::string& value) {
    std::string floor = upper(trim(value));
    if (std::find(FLOOR_ORDER.begin(), FLOOR_ORDER.end(), floor) != FLOOR_ORDER.end()) return floor;
    return std::nullopt;
}

static std::optional<std::string> norm_side(const std::string& value) {
    std::string side = upper(trim(value));
    if (starts_with(side, 'L')) return "L";
    if (starts_with(side, 'R')) return "R";
    return std::nullopt;
}

static int floor_index(const std::string& floor) {
    auto it = std::find(FLOOR_ORDER.begin(), FLOOR_ORDER.end(), floor);
    if (it == FLOOR_ORDER.end()) return 999;
    return static_cast<int>(std::distance(FLOOR_ORDER.begin(), it)) + 1;
}

static std::vector<std::string> sort_floors(std::vector<std::string> floors) {
    std::sort(floors.begin(), floors.end(), [](const auto& a, const auto& b) {
        return floor_index(a) < floor_index(b);
    });
    return floors;
}

static int reversed_aisle(int aisle) {
    return TOTAL_AISLES - aisle + 1;
}

static double x_coord(int aisle) {
    return (SHELF_DEPTH + AISLE_WIDTH / 2.0) + ((reversed_aisle(aisle) - 1) * AISLE_PITCH);
}

static double y_coord(int column) {
    if (column <= 10) {
        return CROSS_AISLE_WIDTH + ((column - 0.5) * COLUMN_LENGTH);
    }
    return CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH + CROSS_AISLE_WIDTH +
           ((column - 10.0 - 0.5) * COLUMN_LENGTH);
}

static double same_floor_distance(Node a, Node b) {
    double x1 = x_coord(a.aisle);
    double y1 = y_coord(a.column);
    double x2 = x_coord(b.aisle);
    double y2 = y_coord(b.column);
    if (a.aisle == b.aisle) return std::abs(y1 - y2);
    double best = std::numeric_limits<double>::infinity();
    for (double cross_y : CROSS_AISLE_CENTERS) {
        best = std::min(best, std::abs(y1 - cross_y) + std::abs(x1 - x2) + std::abs(cross_y - y2));
    }
    return best;
}

static std::pair<double, double> stair_position(int stair_id) {
    int a1 = 5, a2 = 6, cross = 1;
    switch (stair_id) {
        case 1: a1 = 5; a2 = 6; cross = 1; break;
        case 2: a1 = 15; a2 = 16; cross = 1; break;
        case 3: a1 = 24; a2 = 25; cross = 1; break;
        case 4: a1 = 9; a2 = 10; cross = 2; break;
        case 5: a1 = 19; a2 = 20; cross = 2; break;
        case 6: a1 = 4; a2 = 5; cross = 3; break;
        case 7: a1 = 14; a2 = 15; cross = 3; break;
        case 8: a1 = 23; a2 = 24; cross = 3; break;
        default: break;
    }
    double x = (x_coord(a1) + x_coord(a2)) / 2.0;
    double y = cross == 1 ? CROSS_AISLE_WIDTH
                          : (cross == 2 ? CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH
                                        : CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH +
                                              CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH);
    return {x, y};
}

static int nearest_elevator(int aisle) {
    return std::abs(aisle - 8) <= std::abs(aisle - 18) ? 1 : 2;
}

static int elevator_aisle(int elevator) {
    return elevator == 1 ? 8 : 18;
}

static int nearest_stair_to_elevator(int elevator) {
    double elevator_x = x_coord(elevator_aisle(elevator));
    int best_id = 1;
    double best_distance = std::numeric_limits<double>::infinity();
    for (int stair_id : {1, 2, 3}) {
        auto [stair_x, ignored] = stair_position(stair_id);
        (void)ignored;
        double distance = std::abs(stair_x - elevator_x);
        if (distance < best_distance) {
            best_distance = distance;
            best_id = stair_id;
        }
    }
    return best_id;
}

static double entry_exit_distance(Node node) {
    int elevator = nearest_elevator(node.aisle);
    int stair = nearest_stair_to_elevator(elevator);
    auto [stair_x, ignored] = stair_position(stair);
    (void)ignored;
    double elevator_x = x_coord(elevator_aisle(elevator));
    double stair_to_elevator = std::abs(stair_x - elevator_x) + CROSS_AISLE_WIDTH;
    double elevator_to_pick = std::abs(node.aisle - elevator_aisle(elevator)) * AISLE_PITCH;
    if (node.column <= 10) {
        elevator_to_pick += CROSS_AISLE_WIDTH + ((node.column - 0.5) * COLUMN_LENGTH);
    } else {
        elevator_to_pick += CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH + CROSS_AISLE_WIDTH +
                            ((node.column - 10.0 - 0.5) * COLUMN_LENGTH);
    }
    return stair_to_elevator + elevator_to_pick;
}

static double route_cost(const std::vector<Node>& route) {
    if (route.empty()) return 0.0;
    double total = entry_exit_distance(route.front());
    for (std::size_t idx = 0; idx + 1 < route.size(); ++idx) {
        total += same_floor_distance(route[idx], route[idx + 1]);
    }
    return total + entry_exit_distance(route.back());
}

static double edge_cost(std::optional<Node> left, std::optional<Node> right) {
    if (!left && !right) return 0.0;
    if (!left) return entry_exit_distance(*right);
    if (!right) return entry_exit_distance(*left);
    return same_floor_distance(*left, *right);
}

static std::vector<std::pair<double, std::size_t>> insertion_options(const std::vector<Node>& route, Node node) {
    if (route.empty()) return {{2.0 * entry_exit_distance(node), 0}};
    std::vector<std::pair<double, std::size_t>> options;
    options.reserve(route.size() + 1);
    options.push_back({entry_exit_distance(node) + same_floor_distance(node, route.front()) -
                           entry_exit_distance(route.front()),
                       0});
    for (std::size_t idx = 0; idx + 1 < route.size(); ++idx) {
        options.push_back({same_floor_distance(route[idx], node) + same_floor_distance(node, route[idx + 1]) -
                               same_floor_distance(route[idx], route[idx + 1]),
                           idx + 1});
    }
    options.push_back({same_floor_distance(route.back(), node) + entry_exit_distance(node) -
                           entry_exit_distance(route.back()),
                       route.size()});
    std::sort(options.begin(), options.end());
    return options;
}

static std::pair<double, std::size_t> best_insertion(const std::vector<Node>& route, Node node) {
    return insertion_options(route, node).front();
}

static std::tuple<double, std::size_t, std::vector<Node>> strict_best_position_cost(
    const std::vector<Node>& route,
    Node node
) {
    if (route.empty()) return {route_cost({node}), 0, {node}};
    double best_total = std::numeric_limits<double>::infinity();
    std::size_t best_index = 0;
    std::vector<Node> best_route;
    for (std::size_t index = 0; index <= route.size(); ++index) {
        auto trial = route;
        trial.insert(trial.begin() + static_cast<std::ptrdiff_t>(index), node);
        double total = route_cost(trial);
        if (total < best_total - 1e-12 || (std::abs(total - best_total) <= 1e-12 && index < best_index)) {
            best_total = total;
            best_index = index;
            best_route = std::move(trial);
        }
    }
    return {best_total, best_index, best_route};
}

struct State {
    std::vector<int> remaining_stock;
    std::map<std::size_t, int> picks_by_location;
    std::map<int, std::map<std::size_t, int>> picks_by_article;
    std::set<std::string> active_floors;
    std::set<std::string> active_thms;
    std::map<std::string, std::set<Node>> active_nodes_by_floor;
    std::map<std::string, std::vector<Node>> route_by_floor;
    std::map<std::string, double> route_cost_by_floor;

    explicit State(const std::vector<Loc>& locs) {
        remaining_stock.reserve(locs.size());
        for (const auto& loc : locs) remaining_stock.push_back(loc.stock);
    }

    int picked_for_article(int article) const {
        auto it = picks_by_article.find(article);
        if (it == picks_by_article.end()) return 0;
        int total = 0;
        for (const auto& [idx, qty] : it->second) {
            (void)idx;
            total += qty;
        }
        return total;
    }

    int remaining_demand(const std::map<int, int>& demands, int article) const {
        auto it = demands.find(article);
        if (it == demands.end()) return 0;
        return std::max(0, it->second - picked_for_article(article));
    }

    Candidate* fill_candidate(
        Candidate& candidate,
        const std::vector<Loc>& locs,
        Weights weights,
        std::size_t loc_idx,
        int remaining_demand,
        bool strict
    ) const {
        const auto& loc = locs[loc_idx];
        int available = remaining_stock[loc_idx];
        if (available <= 0 || remaining_demand <= 0) return nullptr;
        int take = std::min(available, remaining_demand);
        bool new_floor = active_floors.count(loc.floor) == 0;
        bool new_thm = active_thms.count(loc.thm_id) == 0;
        Node node = loc.node();
        auto node_it = active_nodes_by_floor.find(loc.floor);
        bool new_node = node_it == active_nodes_by_floor.end() || node_it->second.count(node) == 0;

        std::size_t insert_index = route_by_floor.count(loc.floor) ? route_by_floor.at(loc.floor).size() : 0;
        double route_delta = 0.0;
        bool has_route_nodes = false;
        std::vector<Node> route_nodes;
        double route_total_cost = 0.0;

        if (new_node) {
            const auto route_it = route_by_floor.find(loc.floor);
            const std::vector<Node> empty;
            const auto& route = route_it == route_by_floor.end() ? empty : route_it->second;
            if (strict) {
                auto [total, index, new_route] = strict_best_position_cost(route, node);
                double current = route_cost_by_floor.count(loc.floor) ? route_cost_by_floor.at(loc.floor) : 0.0;
                insert_index = index;
                route_delta = total - current;
                has_route_nodes = true;
                route_nodes = std::move(new_route);
                route_total_cost = total;
            } else {
                auto [delta, index] = best_insertion(route, node);
                insert_index = index;
                route_delta = delta;
            }
        }

        double marginal = weights.distance * route_delta + (new_thm ? weights.thm : 0.0) +
                          (new_floor ? weights.floor : 0.0);
        candidate = Candidate{loc_idx,
                              take,
                              marginal / std::max(1, take),
                              marginal,
                              route_delta,
                              insert_index,
                              new_floor,
                              new_thm,
                              new_node,
                              has_route_nodes,
                              std::move(route_nodes),
                              route_total_cost};
        return &candidate;
    }

    std::optional<Candidate> evaluate_candidate(
        const std::vector<Loc>& locs,
        Weights weights,
        std::size_t loc_idx,
        int remaining_demand
    ) const {
        Candidate candidate;
        if (!fill_candidate(candidate, locs, weights, loc_idx, remaining_demand, false)) return std::nullopt;
        return candidate;
    }

    std::optional<Candidate> evaluate_candidate_strict(
        const std::vector<Loc>& locs,
        Weights weights,
        std::size_t loc_idx,
        int remaining_demand
    ) const {
        Candidate candidate;
        if (!fill_candidate(candidate, locs, weights, loc_idx, remaining_demand, true)) return std::nullopt;
        return candidate;
    }

    void commit(const std::vector<Loc>& locs, const Candidate& candidate) {
        const auto& loc = locs[candidate.loc_idx];
        int available = remaining_stock[candidate.loc_idx];
        if (candidate.take <= 0 || candidate.take > available) {
            throw std::runtime_error("invalid commit for " + loc.lid);
        }
        remaining_stock[candidate.loc_idx] -= candidate.take;
        picks_by_location[candidate.loc_idx] += candidate.take;
        picks_by_article[loc.article][candidate.loc_idx] += candidate.take;
        if (candidate.new_floor) active_floors.insert(loc.floor);
        if (candidate.new_thm) active_thms.insert(loc.thm_id);
        if (candidate.new_node) {
            if (candidate.has_route_nodes) {
                route_by_floor[loc.floor] = candidate.route_nodes;
                route_cost_by_floor[loc.floor] =
                    candidate.route_total_cost != 0.0 ? candidate.route_total_cost : route_cost(candidate.route_nodes);
            } else {
                auto& route = route_by_floor[loc.floor];
                route.insert(route.begin() + static_cast<std::ptrdiff_t>(candidate.insert_index), loc.node());
                route_cost_by_floor[loc.floor] += candidate.route_delta;
            }
            active_nodes_by_floor[loc.floor].insert(loc.node());
        }
    }
};

static std::optional<Node> node_at(const std::vector<Node>& route, int index) {
    if (index < 0 || static_cast<std::size_t>(index) >= route.size()) return std::nullopt;
    return route[static_cast<std::size_t>(index)];
}

static std::optional<Node> node_after_swap(const std::vector<Node>& route, int index, std::size_t left, std::size_t right) {
    if (index < 0 || static_cast<std::size_t>(index) >= route.size()) return std::nullopt;
    std::size_t idx = static_cast<std::size_t>(index);
    if (idx == left) return route[right];
    if (idx == right) return route[left];
    return route[idx];
}

static double two_opt_delta(const std::vector<Node>& route, std::size_t left, std::size_t right) {
    auto prev = node_at(route, static_cast<int>(left) - 1);
    auto next = node_at(route, static_cast<int>(right) + 1);
    return edge_cost(prev, route[right]) + edge_cost(route[left], next) -
           edge_cost(prev, route[left]) - edge_cost(route[right], next);
}

static double swap_delta(const std::vector<Node>& route, std::size_t left, std::size_t right) {
    std::vector<int> edges = {static_cast<int>(left) - 1,
                              static_cast<int>(left),
                              static_cast<int>(right) - 1,
                              static_cast<int>(right)};
    std::set<int> seen;
    double old_cost = 0.0;
    double new_cost = 0.0;
    for (int edge_left : edges) {
        if (!seen.insert(edge_left).second) continue;
        if (edge_left < -1 || static_cast<std::size_t>(edge_left) >= route.size()) continue;
        old_cost += edge_cost(node_at(route, edge_left), node_at(route, edge_left + 1));
        new_cost += edge_cost(
            node_after_swap(route, edge_left, left, right),
            node_after_swap(route, edge_left + 1, left, right)
        );
    }
    return new_cost - old_cost;
}

static double relocate_delta(const std::vector<Node>& route, std::size_t source, std::size_t target) {
    Node node = route[source];
    auto prev = node_at(route, static_cast<int>(source) - 1);
    auto next = node_at(route, static_cast<int>(source) + 1);
    double removal = edge_cost(prev, next) - edge_cost(prev, node) - edge_cost(node, next);
    auto without = route;
    without.erase(without.begin() + static_cast<std::ptrdiff_t>(source));
    auto prev_insert = target > 0 ? std::optional<Node>(without[target - 1]) : std::nullopt;
    auto next_insert = target < without.size() ? std::optional<Node>(without[target]) : std::nullopt;
    double insert = edge_cost(prev_insert, node) + edge_cost(node, next_insert) - edge_cost(prev_insert, next_insert);
    return removal + insert;
}

static std::vector<Node> cleanup_route_delta(
    const std::vector<Node>& route,
    std::string op,
    const std::string& strategy,
    std::size_t max_passes
) {
    std::transform(op.begin(), op.end(), op.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    std::replace(op.begin(), op.end(), '_', '-');
    if (op == "none" || op == "noop" || op == "no-op") return route;
    if (op == "two-opt" || op == "2opt") op = "2-opt";
    if (op != "2-opt" && op != "swap" && op != "relocate") throw std::runtime_error("unsupported cleanup operator");
    if (strategy != "first" && strategy != "best") throw std::runtime_error("unsupported cleanup strategy");

    auto improved = route;
    if (improved.size() <= 1 || (op == "2-opt" && improved.size() <= 2)) return improved;

    for (std::size_t pass = 0; pass < max_passes; ++pass) {
        bool applied = false;
        std::optional<std::tuple<double, std::size_t, std::size_t>> best_move;
        if (op == "2-opt") {
            for (std::size_t left = 0; left + 1 < improved.size(); ++left) {
                for (std::size_t right = left + 1; right < improved.size(); ++right) {
                    double delta = two_opt_delta(improved, left, right);
                    if (delta < -EPS) {
                        if (strategy == "first") {
                            std::reverse(improved.begin() + static_cast<std::ptrdiff_t>(left),
                                         improved.begin() + static_cast<std::ptrdiff_t>(right + 1));
                            applied = true;
                            break;
                        }
                        if (!best_move || delta < std::get<0>(*best_move) - 1e-12) best_move = {delta, left, right};
                    }
                }
                if (applied) break;
            }
            if (strategy == "best" && best_move) {
                auto [ignored, left, right] = *best_move;
                (void)ignored;
                std::reverse(improved.begin() + static_cast<std::ptrdiff_t>(left),
                             improved.begin() + static_cast<std::ptrdiff_t>(right + 1));
                applied = true;
            }
        } else if (op == "swap") {
            for (std::size_t left = 0; left + 1 < improved.size(); ++left) {
                for (std::size_t right = left + 1; right < improved.size(); ++right) {
                    double delta = swap_delta(improved, left, right);
                    if (delta < -EPS) {
                        if (strategy == "first") {
                            std::swap(improved[left], improved[right]);
                            applied = true;
                            break;
                        }
                        if (!best_move || delta < std::get<0>(*best_move) - 1e-12) best_move = {delta, left, right};
                    }
                }
                if (applied) break;
            }
            if (strategy == "best" && best_move) {
                auto [ignored, left, right] = *best_move;
                (void)ignored;
                std::swap(improved[left], improved[right]);
                applied = true;
            }
        } else {
            for (std::size_t source = 0; source < improved.size(); ++source) {
                for (std::size_t target = 0; target < improved.size(); ++target) {
                    if (target == source) continue;
                    double delta = relocate_delta(improved, source, target);
                    if (delta < -EPS) {
                        if (strategy == "first") {
                            Node node = improved[source];
                            improved.erase(improved.begin() + static_cast<std::ptrdiff_t>(source));
                            improved.insert(improved.begin() + static_cast<std::ptrdiff_t>(target), node);
                            applied = true;
                            break;
                        }
                        if (!best_move || delta < std::get<0>(*best_move) - 1e-12) best_move = {delta, source, target};
                    }
                }
                if (applied) break;
            }
            if (strategy == "best" && best_move) {
                auto [ignored, source, target] = *best_move;
                (void)ignored;
                Node node = improved[source];
                improved.erase(improved.begin() + static_cast<std::ptrdiff_t>(source));
                improved.insert(improved.begin() + static_cast<std::ptrdiff_t>(target), node);
                applied = true;
            }
        }
        if (!applied) break;
    }
    return improved;
}

static std::vector<Node> build_route(const std::set<Node>& nodes, bool use_regret) {
    std::set<Node> unique = nodes;
    if (unique.size() <= 1) return {unique.begin(), unique.end()};
    auto seed_it = std::max_element(unique.begin(), unique.end(), [](Node a, Node b) {
        double da = entry_exit_distance(a);
        double db = entry_exit_distance(b);
        if (da != db) return da < db;
        if (a.aisle != b.aisle) return a.aisle > b.aisle;
        return a.column > b.column;
    });
    std::vector<Node> route = {*seed_it};
    unique.erase(*seed_it);

    while (!unique.empty()) {
        struct Eval {
            double regret;
            double best_delta;
            Node node;
            std::size_t index;
        };
        std::vector<Eval> evaluated;
        for (Node node : unique) {
            auto options = insertion_options(route, node);
            double best_delta = options[0].first;
            std::size_t best_index = options[0].second;
            double second_delta = options.size() > 1 ? options[1].first : best_delta;
            evaluated.push_back({second_delta - best_delta, best_delta, node, best_index});
        }
        std::sort(evaluated.begin(), evaluated.end(), [use_regret](const Eval& a, const Eval& b) {
            if (use_regret) {
                if (a.regret != b.regret) return a.regret > b.regret;
                if (a.best_delta != b.best_delta) return a.best_delta < b.best_delta;
            } else {
                if (a.best_delta != b.best_delta) return a.best_delta < b.best_delta;
                if (a.regret != b.regret) return a.regret > b.regret;
            }
            return std::tie(a.node.aisle, a.node.column) < std::tie(b.node.aisle, b.node.column);
        });
        const auto chosen = evaluated.front();
        route.insert(route.begin() + static_cast<std::ptrdiff_t>(chosen.index), chosen.node);
        unique.erase(chosen.node);
    }
    return route;
}

static std::vector<Node> two_opt_route(std::vector<Node> route, std::size_t max_passes) {
    if (route.size() <= 2) return route;
    for (std::size_t pass = 0; pass < max_passes; ++pass) {
        bool improved = false;
        for (std::size_t i = 0; i + 1 < route.size(); ++i) {
            auto prev = i > 0 ? std::optional<Node>(route[i - 1]) : std::nullopt;
            for (std::size_t j = i + 1; j < route.size(); ++j) {
                auto next = j + 1 < route.size() ? std::optional<Node>(route[j + 1]) : std::nullopt;
                double old_cost = edge_cost(prev, route[i]) + edge_cost(route[j], next);
                double new_cost = edge_cost(prev, route[j]) + edge_cost(route[i], next);
                if (new_cost + EPS < old_cost) {
                    std::reverse(route.begin() + static_cast<std::ptrdiff_t>(i),
                                 route.begin() + static_cast<std::ptrdiff_t>(j + 1));
                    improved = true;
                }
            }
        }
        if (!improved) break;
    }
    return route;
}

static std::vector<Node> seed_route_from_hint(const std::set<Node>& nodes, const std::vector<Node>& hint) {
    std::vector<Node> route;
    std::set<Node> seen;
    for (Node node : hint) {
        if (nodes.count(node) && seen.insert(node).second) route.push_back(node);
    }
    for (Node node : nodes) {
        if (seen.insert(node).second) {
            auto [ignored, index] = best_insertion(route, node);
            (void)ignored;
            route.insert(route.begin() + static_cast<std::ptrdiff_t>(index), node);
        }
    }
    return route;
}

static bool loc_less(const Loc& a, const Loc& b) {
    return std::make_tuple(floor_index(a.floor), a.aisle, a.column, a.shelf, a.side, a.thm_id, a.lid) <
           std::make_tuple(floor_index(b.floor), b.aisle, b.column, b.shelf, b.side, b.thm_id, b.lid);
}

static bool candidate_less(const Candidate& a, const Candidate& b, const std::vector<Loc>& locs) {
    const auto& la = locs[a.loc_idx];
    const auto& lb = locs[b.loc_idx];
    return std::make_tuple(a.unit_cost,
                           a.marginal_cost,
                           a.new_floor,
                           a.new_thm,
                           a.new_node,
                           a.route_delta,
                           -a.take,
                           floor_index(la.floor),
                           la.aisle,
                           la.column,
                           la.shelf,
                           la.side,
                           la.thm_id,
                           la.lid) <
           std::make_tuple(b.unit_cost,
                           b.marginal_cost,
                           b.new_floor,
                           b.new_thm,
                           b.new_node,
                           b.route_delta,
                           -b.take,
                           floor_index(lb.floor),
                           lb.aisle,
                           lb.column,
                           lb.shelf,
                           lb.side,
                           lb.thm_id,
                           lb.lid);
}

static std::map<int, int> load_demands(const fs::path& path) {
    std::map<int, int> demands;
    for (const auto& row : read_csv(path)) {
        auto article_it = row.find("ARTICLE_CODE");
        auto amount_it = row.find("AMOUNT");
        if (article_it == row.end() || amount_it == row.end()) continue;
        auto article = parse_i32(article_it->second);
        auto amount = parse_i32(amount_it->second);
        if (!article || !amount) continue;
        if (*amount < 0) throw std::runtime_error("negative demand for article " + std::to_string(*article));
        demands[*article] += *amount;
    }
    return demands;
}

static std::vector<Loc> load_stock(const fs::path& path) {
    using AggKey = std::tuple<std::string, int, std::string, int, std::string, int, int>;
    std::map<AggKey, int> aggregated;
    for (const auto& row : read_csv(path)) {
        auto get = [&](const std::string& key) -> std::string {
            auto it = row.find(key);
            return it == row.end() ? "" : it->second;
        };
        auto article = parse_i32(get("ARTICLE_CODE"));
        auto aisle = parse_i32(get("AISLE"));
        auto column = parse_i32(get("COLUMN"));
        auto shelf = parse_i32(get("SHELF"));
        auto stock = parse_i32(get("STOCK").empty() ? get("STOCK_AMOUNT") : get("STOCK"));
        auto floor = norm_floor(get("FLOOR"));
        auto side = norm_side(!get("RIGHT_OR_LEFT").empty() ? get("RIGHT_OR_LEFT") : get("LEFT_OR_RIGHT"));
        std::string thm = trim(get("THM_ID"));
        if (!article || !aisle || !column || !shelf || !stock || !floor || !side) continue;
        if (thm.empty() || *stock <= 0) continue;
        if (*aisle < 1 || *aisle > TOTAL_AISLES || *column < 1 || *column > TOTAL_COLUMNS) continue;
        aggregated[{thm, *article, *floor, *aisle, *side, *column, *shelf}] += *stock;
    }

    std::vector<Loc> locs;
    std::size_t index = 1;
    for (const auto& [key, stock] : aggregated) {
        const auto& [thm, article, floor, aisle, side, column, shelf] = key;
        std::ostringstream lid;
        lid << 'j' << std::setw(5) << std::setfill('0') << index++;
        locs.push_back(Loc{lid.str(), thm, article, floor, aisle, side, column, shelf, stock});
    }
    return locs;
}

static Problem prepare_problem(
    const fs::path& orders,
    const fs::path& stock,
    const std::optional<std::set<std::string>>& floor_filter,
    const std::optional<std::set<int>>& article_filter
) {
    Problem problem;
    problem.demands = load_demands(orders);
    if (article_filter) {
        for (auto it = problem.demands.begin(); it != problem.demands.end();) {
            if (!article_filter->count(it->first)) it = problem.demands.erase(it);
            else ++it;
        }
    }
    if (problem.demands.empty()) throw std::runtime_error("no demanded articles after filters");

    auto all_locs = load_stock(stock);
    for (const auto& loc : all_locs) {
        if (!problem.demands.count(loc.article)) continue;
        if (floor_filter && !floor_filter->count(loc.floor)) continue;
        problem.locs.push_back(loc);
    }

    std::map<int, int> stock_by_article;
    for (std::size_t idx = 0; idx < problem.locs.size(); ++idx) {
        const auto& loc = problem.locs[idx];
        problem.article_to_candidates[loc.article].push_back(idx);
        stock_by_article[loc.article] += loc.stock;
    }
    for (const auto& [article, demand] : problem.demands) {
        if (!problem.article_to_candidates.count(article)) {
            throw std::runtime_error("no stock rows found for demanded article " + std::to_string(article));
        }
        if (stock_by_article[article] < demand) {
            throw std::runtime_error("insufficient stock for article " + std::to_string(article));
        }
    }
    for (auto& [article, candidates] : problem.article_to_candidates) {
        (void)article;
        std::sort(candidates.begin(), candidates.end(), [&](std::size_t a, std::size_t b) {
            return loc_less(problem.locs[a], problem.locs[b]);
        });
    }
    return problem;
}

struct ArticleRank {
    int candidate_count = 0;
    int floor_count = 0;
    double regret_rank = 0.0;
    int node_count = 0;
    int slack = 0;
    int neg_demand = 0;
    int article = 0;
};

static bool article_rank_less(const ArticleRank& a, const ArticleRank& b) {
    return std::tie(a.candidate_count, a.floor_count, a.regret_rank, a.node_count, a.slack, a.neg_demand, a.article) <
           std::tie(b.candidate_count, b.floor_count, b.regret_rank, b.node_count, b.slack, b.neg_demand, b.article);
}

static std::vector<int> compute_article_order(
    const std::map<int, int>& remaining,
    const Problem& problem,
    Weights weights
) {
    std::vector<std::pair<ArticleRank, int>> ranked;
    for (const auto& [article, demand] : remaining) {
        const auto& candidates = problem.article_to_candidates.at(article);
        int total_stock = 0;
        std::set<std::string> floors;
        std::set<std::tuple<std::string, int, int>> nodes;
        struct Base {
            double unit;
            double cost;
            int neg_take;
            int floor_idx;
            int aisle;
            int column;
            int shelf;
            std::string thm;
            std::string lid;
        };
        std::vector<Base> base_scores;
        for (auto idx : candidates) {
            const auto& loc = problem.locs[idx];
            total_stock += loc.stock;
            floors.insert(loc.floor);
            nodes.insert({loc.floor, loc.aisle, loc.column});
            int take = std::max(1, std::min(demand, loc.stock));
            double base_cost = weights.distance * (2.0 * entry_exit_distance(loc.node())) + weights.thm + weights.floor;
            base_scores.push_back({base_cost / take,
                                   base_cost,
                                   -take,
                                   floor_index(loc.floor),
                                   loc.aisle,
                                   loc.column,
                                   loc.shelf,
                                   loc.thm_id,
                                   loc.lid});
        }
        std::sort(base_scores.begin(), base_scores.end(), [](const Base& a, const Base& b) {
            return std::tie(a.unit, a.cost, a.neg_take, a.floor_idx, a.aisle, a.column, a.shelf, a.thm, a.lid) <
                   std::tie(b.unit, b.cost, b.neg_take, b.floor_idx, b.aisle, b.column, b.shelf, b.thm, b.lid);
        });
        double regret_rank = base_scores.size() == 1
                                 ? -1e18
                                 : -std::max(0.0, base_scores[1].unit - base_scores[0].unit);
        ranked.push_back({ArticleRank{static_cast<int>(candidates.size()),
                                      static_cast<int>(floors.size()),
                                      regret_rank,
                                      static_cast<int>(nodes.size()),
                                      total_stock - demand,
                                      -demand,
                                      article},
                          article});
    }
    std::sort(ranked.begin(), ranked.end(), [](const auto& a, const auto& b) {
        return article_rank_less(a.first, b.first);
    });
    std::vector<int> order;
    for (const auto& [rank, article] : ranked) {
        (void)rank;
        order.push_back(article);
    }
    return order;
}

static std::vector<Candidate> build_rcl(const std::vector<Candidate>& scored, double alpha, std::size_t max_size) {
    if (scored.empty()) return {};
    std::size_t limit = std::min(std::max<std::size_t>(1, max_size), scored.size());
    std::vector<Candidate> prefix(scored.begin(), scored.begin() + static_cast<std::ptrdiff_t>(limit));
    double best = prefix.front().unit_cost;
    double worst = prefix.back().unit_cost;
    if (std::abs(best - worst) <= 1e-12) return prefix;
    alpha = std::clamp(alpha, 0.0, 1.0);
    double threshold = best + alpha * (worst - best);
    std::vector<Candidate> rcl;
    for (const auto& candidate : prefix) {
        if (candidate.unit_cost <= threshold + 1e-12) rcl.push_back(candidate);
    }
    if (rcl.empty()) rcl.push_back(prefix.front());
    return rcl;
}

static const Candidate& weighted_choice(const std::vector<Candidate>& rcl, SimpleRng& rng) {
    if (rcl.size() == 1) return rcl.front();
    std::size_t total = rcl.size() * (rcl.size() + 1) / 2;
    std::size_t draw = rng.randrange(total);
    for (std::size_t idx = 0; idx < rcl.size(); ++idx) {
        std::size_t weight = rcl.size() - idx;
        if (draw < weight) return rcl[idx];
        draw -= weight;
    }
    return rcl.front();
}

static FallbackSummary complete_with_grasp_fallback(
    State& state,
    const Problem& problem,
    Weights weights,
    double alpha,
    std::size_t article_rcl_size,
    std::size_t location_rcl_size,
    std::uint64_t seed
) {
    SimpleRng rng(seed);
    std::map<int, int> remaining_demands;
    for (const auto& [article, demand] : problem.demands) {
        (void)demand;
        int remaining = state.remaining_demand(problem.demands, article);
        if (remaining > 0) remaining_demands[article] = remaining;
    }
    auto remaining_articles = compute_article_order(remaining_demands, problem, weights);
    FallbackSummary summary;
    summary.rule = "GRASP-style article RCL + location RCL";

    while (!remaining_articles.empty()) {
        std::size_t limit = std::min(std::max<std::size_t>(1, article_rcl_size), remaining_articles.size());
        std::size_t article_index = rng.randrange(limit);
        int article = remaining_articles[article_index];
        remaining_articles.erase(remaining_articles.begin() + static_cast<std::ptrdiff_t>(article_index));
        while (true) {
            int remaining = state.remaining_demand(problem.demands, article);
            if (remaining <= 0) break;
            std::vector<Candidate> scored;
            for (auto loc_idx : problem.article_to_candidates.at(article)) {
                summary.candidate_evals++;
                auto candidate = state.evaluate_candidate(problem.locs, weights, loc_idx, remaining);
                if (candidate) scored.push_back(*candidate);
            }
            if (scored.empty()) throw std::runtime_error("no feasible fallback candidate");
            std::sort(scored.begin(), scored.end(), [&](const auto& a, const auto& b) {
                return candidate_less(a, b, problem.locs);
            });
            auto rcl = build_rcl(scored, alpha, location_rcl_size);
            Candidate chosen = weighted_choice(rcl, rng);
            state.commit(problem.locs, chosen);
            summary.steps++;
        }
        summary.articles++;
    }
    return summary;
}

using BoxKey = std::tuple<std::string, int, int, int, std::string>;
using HalfBlockKey = std::tuple<std::string, int, int>;
using AisleKey = std::tuple<std::string, int>;

static BoxKey box_key(const Loc& loc) {
    return {loc.floor, loc.aisle, loc.column, loc.shelf, loc.side};
}

static HalfBlockKey half_block_key(const Loc& loc) {
    return {loc.floor, loc.aisle, loc.column <= 10 ? 1 : 2};
}

static AisleKey aisle_key(const Loc& loc) {
    return {loc.floor, loc.aisle};
}

static FallbackSummary complete_with_visited_area_fallback(
    State& state,
    const Problem& problem,
    Weights weights,
    std::uint64_t seed
) {
    SimpleRng rng(seed);
    std::vector<int> remaining_articles;
    for (const auto& [article, demand] : problem.demands) {
        (void)demand;
        if (state.remaining_demand(problem.demands, article) > 0) remaining_articles.push_back(article);
    }
    std::sort(remaining_articles.begin(), remaining_articles.end());

    FallbackSummary summary;
    summary.rule = "visited box -> visited half-block -> visited aisle -> visited floor -> random";
    while (!remaining_articles.empty()) {
        int article = remaining_articles.front();
        remaining_articles.erase(remaining_articles.begin());
        while (true) {
            int remaining = state.remaining_demand(problem.demands, article);
            if (remaining <= 0) break;
            std::vector<std::size_t> feasible;
            for (auto idx : problem.article_to_candidates.at(article)) {
                if (state.remaining_stock[idx] > 0) feasible.push_back(idx);
            }
            summary.candidate_evals += feasible.size();
            if (feasible.empty()) throw std::runtime_error("no feasible visited-area fallback candidate");

            std::set<BoxKey> visited_boxes;
            std::set<HalfBlockKey> visited_half_blocks;
            std::set<AisleKey> visited_aisles;
            for (const auto& [idx, qty] : state.picks_by_location) {
                if (qty <= 0) continue;
                const auto& loc = problem.locs[idx];
                visited_boxes.insert(box_key(loc));
                visited_half_blocks.insert(half_block_key(loc));
                visited_aisles.insert(aisle_key(loc));
            }

            std::optional<std::size_t> chosen;
            for (auto idx : feasible) {
                if (visited_boxes.count(box_key(problem.locs[idx]))) {
                    chosen = idx;
                    summary.visited_box_hits++;
                    break;
                }
            }
            if (!chosen) {
                for (auto idx : feasible) {
                    if (visited_half_blocks.count(half_block_key(problem.locs[idx]))) {
                        chosen = idx;
                        summary.visited_half_block_hits++;
                        break;
                    }
                }
            }
            if (!chosen) {
                for (auto idx : feasible) {
                    if (visited_aisles.count(aisle_key(problem.locs[idx]))) {
                        chosen = idx;
                        summary.visited_aisle_hits++;
                        break;
                    }
                }
            }
            if (!chosen) {
                for (auto idx : feasible) {
                    if (state.active_floors.count(problem.locs[idx].floor)) {
                        chosen = idx;
                        summary.visited_floor_hits++;
                        break;
                    }
                }
            }
            if (!chosen) {
                summary.random_hits++;
                chosen = feasible[rng.randrange(feasible.size())];
            }
            auto candidate = state.evaluate_candidate(problem.locs, weights, *chosen, remaining);
            if (!candidate) throw std::runtime_error("visited-area fallback selected infeasible location");
            state.commit(problem.locs, *candidate);
            summary.steps++;
        }
        summary.articles++;
    }
    return summary;
}

static Solution build_solution_from_state(
    const std::string& algorithm,
    const Problem& problem,
    const State& state,
    Weights weights,
    double solve_time
) {
    std::map<std::string, std::map<std::size_t, int>> picks_by_floor;
    std::map<std::string, std::set<Node>> active_nodes_by_floor;
    for (const auto& [idx, qty] : state.picks_by_location) {
        if (qty <= 0) continue;
        const auto& loc = problem.locs[idx];
        picks_by_floor[loc.floor][idx] = qty;
        active_nodes_by_floor[loc.floor].insert(loc.node());
    }

    std::vector<std::string> floors;
    for (const auto& [floor, picks] : picks_by_floor) {
        (void)picks;
        floors.push_back(floor);
    }
    floors = sort_floors(floors);

    Solution solution;
    solution.algorithm = algorithm;
    solution.solve_time = solve_time;
    std::set<std::string> all_thms;
    for (const auto& floor : floors) {
        auto nodes = active_nodes_by_floor[floor];
        std::vector<Node> route;
        if (nodes.size() <= 60) {
            route = build_route(nodes, true);
        } else {
            auto hint_it = state.route_by_floor.find(floor);
            route = seed_route_from_hint(nodes, hint_it == state.route_by_floor.end() ? std::vector<Node>{} : hint_it->second);
        }
        if (route.empty() && !nodes.empty()) route = build_route(nodes, true);

        FloorResult result;
        result.floor = floor;
        result.picks = picks_by_floor[floor];
        result.route = route;
        result.route_distance = route_cost(route);
        for (const auto& [idx, qty] : result.picks) {
            (void)qty;
            result.opened_thms.insert(problem.locs[idx].thm_id);
            all_thms.insert(problem.locs[idx].thm_id);
        }
        solution.floor_results.push_back(std::move(result));
    }
    solution.total_distance = 0.0;
    solution.total_picks = 0;
    for (const auto& floor : solution.floor_results) {
        solution.total_distance += floor.route_distance;
        solution.total_picks += floor.picks.size();
    }
    solution.total_floors = solution.floor_results.size();
    solution.total_thms = all_thms.size();
    solution.objective = weights.distance * solution.total_distance + weights.thm * solution.total_thms +
                         weights.floor * solution.total_floors;
    return solution;
}

static void cleanup_solution_routes(
    Solution& solution,
    const std::vector<Loc>& locs,
    Weights weights,
    const std::string& op,
    const std::string& strategy,
    std::size_t max_passes
) {
    for (auto& floor : solution.floor_results) {
        floor.route = cleanup_route_delta(floor.route, op, strategy, max_passes);
        floor.route_distance = route_cost(floor.route);
    }
    std::set<std::string> all_thms;
    solution.total_distance = 0.0;
    solution.total_picks = 0;
    for (const auto& floor : solution.floor_results) {
        solution.total_distance += floor.route_distance;
        solution.total_picks += floor.picks.size();
        all_thms.insert(floor.opened_thms.begin(), floor.opened_thms.end());
        std::set<Node> route_nodes(floor.route.begin(), floor.route.end());
        for (const auto& [idx, qty] : floor.picks) {
            (void)qty;
            if (!route_nodes.count(locs[idx].node())) {
                throw std::runtime_error("route for " + floor.floor + " misses selected node");
            }
        }
    }
    solution.total_floors = solution.floor_results.size();
    solution.total_thms = all_thms.size();
    solution.objective = weights.distance * solution.total_distance + weights.thm * solution.total_thms +
                         weights.floor * solution.total_floors;
    solution.algorithm += ", " + op + " cleanup (" + strategy + ")";
}

static std::pair<Solution, std::map<std::string, std::string>> solve_current_best(
    const Problem& problem,
    Weights weights,
    std::optional<Clock::time_point> deadline,
    const Args& args,
    Clock::time_point started
) {
    auto prep_start = Clock::now();
    State state(problem.locs);
    std::map<int, std::size_t> counts;
    for (const auto& [article, candidates] : problem.article_to_candidates) counts[article] = candidates.size();

    for (const auto& [article, count] : counts) {
        if (count != 1) continue;
        auto loc_idx = problem.article_to_candidates.at(article).front();
        int remaining = problem.demands.at(article);
        while (remaining > 0) {
            auto candidate = state.evaluate_candidate(problem.locs, weights, loc_idx, remaining);
            if (!candidate) throw std::runtime_error("single-location article has no feasible stock");
            remaining -= candidate->take;
            state.commit(problem.locs, *candidate);
        }
    }
    double prep_elapsed = std::chrono::duration<double>(Clock::now() - prep_start).count();

    auto seed_start = Clock::now();
    std::vector<std::string> seed_floors;
    for (const auto& [floor, nodes] : state.active_nodes_by_floor) {
        (void)nodes;
        seed_floors.push_back(floor);
    }
    for (const auto& floor : seed_floors) {
        auto route = build_route(state.active_nodes_by_floor[floor], true);
        route = two_opt_route(route, 3);
        state.route_by_floor[floor] = route;
        state.route_cost_by_floor[floor] = route_cost(route);
    }
    double seed_elapsed = std::chrono::duration<double>(Clock::now() - seed_start).count();

    auto grouped_start = Clock::now();
    bool timed_out = false;
    std::size_t timeout_group = 0;
    int timeout_article = 0;
    std::size_t fast_reuse_steps = 0;
    std::size_t strict_steps = 0;
    std::size_t strict_candidate_evals = 0;
    std::size_t strict_position_evals = 0;

    std::map<std::size_t, std::vector<int>> groups;
    for (const auto& [article, count] : counts) {
        if (count >= 2) groups[count].push_back(article);
    }

    bool break_groups = false;
    for (const auto& [group_size, articles] : groups) {
        for (int article : articles) {
            int remaining = state.remaining_demand(problem.demands, article);
            while (remaining > 0) {
                if (deadline && Clock::now() >= *deadline) {
                    timed_out = true;
                    timeout_group = group_size;
                    timeout_article = article;
                    break_groups = true;
                    break;
                }
                std::vector<std::size_t> feasible;
                for (auto idx : problem.article_to_candidates.at(article)) {
                    if (state.remaining_stock[idx] > 0) feasible.push_back(idx);
                }
                std::vector<std::size_t> open_thm_locs;
                for (auto idx : feasible) {
                    if (state.active_thms.count(problem.locs[idx].thm_id)) open_thm_locs.push_back(idx);
                }
                if (!open_thm_locs.empty()) {
                    std::vector<Candidate> scored;
                    for (auto idx : open_thm_locs) {
                        auto candidate = state.evaluate_candidate(problem.locs, weights, idx, remaining);
                        if (candidate) scored.push_back(*candidate);
                    }
                    std::sort(scored.begin(), scored.end(), [&](const auto& a, const auto& b) {
                        return candidate_less(a, b, problem.locs);
                    });
                    if (scored.empty()) throw std::runtime_error("open-THM candidate disappeared");
                    Candidate best = scored.front();
                    remaining -= best.take;
                    state.commit(problem.locs, best);
                    fast_reuse_steps++;
                    continue;
                }

                std::vector<Candidate> scored;
                for (auto idx : feasible) {
                    strict_candidate_evals++;
                    const auto& loc = problem.locs[idx];
                    std::size_t route_len = state.route_by_floor.count(loc.floor) ? state.route_by_floor[loc.floor].size() : 0;
                    bool is_new_node = state.active_nodes_by_floor[loc.floor].count(loc.node()) == 0;
                    if (is_new_node) strict_position_evals += route_len + 1;
                    auto candidate = state.evaluate_candidate_strict(problem.locs, weights, idx, remaining);
                    if (candidate) scored.push_back(*candidate);
                }
                if (scored.empty()) throw std::runtime_error("no feasible strict candidate");
                std::sort(scored.begin(), scored.end(), [&](const auto& a, const auto& b) {
                    return candidate_less(a, b, problem.locs);
                });
                Candidate best = scored.front();
                remaining -= best.take;
                state.commit(problem.locs, best);
                strict_steps++;
            }
            if (break_groups) break;
        }
        if (break_groups) break;
    }

    std::map<int, int> remaining_before_fallback;
    for (const auto& [article, demand] : problem.demands) {
        (void)demand;
        int remaining = state.remaining_demand(problem.demands, article);
        if (remaining > 0) remaining_before_fallback[article] = remaining;
    }

    FallbackSummary fallback_summary;
    if (timed_out && args.fallback_on_time_limit) {
        if (args.fallback_method == "visited-area") {
            fallback_summary = complete_with_visited_area_fallback(state, problem, weights, args.fallback_seed);
        } else if (args.fallback_method == "grasp") {
            fallback_summary = complete_with_grasp_fallback(state,
                                                            problem,
                                                            weights,
                                                            args.fallback_alpha,
                                                            args.fallback_article_rcl_size,
                                                            args.fallback_location_rcl_size,
                                                            args.fallback_seed);
        } else {
            throw std::runtime_error("unsupported fallback method");
        }
    }

    double construction_time = std::chrono::duration<double>(Clock::now() - started).count();
    std::map<std::string, std::string> notes;
    auto put = [&](const std::string& key, const auto& value) {
        std::ostringstream out;
        out << value;
        notes[key] = out.str();
    };
    put("seed_route", "pure C++ regret insertion + 2-opt (LK package not used)");
    put("time_limit_sec", args.time_limit);
    put("timed_out", timed_out ? "true" : "false");
    put("timeout_group", timeout_group);
    put("timeout_article", timeout_article);
    put("fallback_on_time_limit", args.fallback_on_time_limit ? "true" : "false");
    put("fallback_used", (timed_out && args.fallback_on_time_limit) ? "true" : "false");
    put("fallback_method", args.fallback_method);
    put("fallback_rule", fallback_summary.rule);
    put("remaining_articles_before_fallback", remaining_before_fallback.size());
    int remaining_units = 0;
    for (const auto& [article, qty] : remaining_before_fallback) {
        (void)article;
        remaining_units += qty;
    }
    put("remaining_units_before_fallback", remaining_units);
    put("fast_reuse_steps", fast_reuse_steps);
    put("strict_steps", strict_steps);
    put("strict_candidate_evals", strict_candidate_evals);
    put("strict_position_evals", strict_position_evals);
    put("fallback_articles", fallback_summary.articles);
    put("fallback_steps", fallback_summary.steps);
    put("fallback_candidate_evals", fallback_summary.candidate_evals);
    put("fallback_visited_box_hits", fallback_summary.visited_box_hits);
    put("fallback_visited_half_block_hits", fallback_summary.visited_half_block_hits);
    put("fallback_visited_aisle_hits", fallback_summary.visited_aisle_hits);
    put("fallback_visited_floor_hits", fallback_summary.visited_floor_hits);
    put("fallback_random_hits", fallback_summary.random_hits);
    put("prep_single_location_sec", fixed6(prep_elapsed));
    put("seed_route_sec", fixed6(seed_elapsed));
    put("ascending_grouped_phase_sec", fixed6(std::chrono::duration<double>(Clock::now() - grouped_start).count()));

    std::string fallback_label = args.fallback_method == "visited-area" ? "visited-area fallback" : "GRASP fallback";
    auto solution = build_solution_from_state(
        "C++ current-best: grouped insertion + open THM shortcut + " + fallback_label,
        problem,
        state,
        weights,
        construction_time
    );
    return {solution, notes};
}

static void write_pick_csv(const Solution& solution, const std::vector<Loc>& locs, const fs::path& path) {
    ensure_parent(path);
    struct PickRow {
        std::string picker_id;
        std::string thm_id;
        int article;
        std::string floor;
        int aisle;
        int column;
        int shelf;
        std::string side;
        int amount;
        std::string pickcar_id;
        std::size_t pick_order;
    };
    std::vector<PickRow> rows;
    for (const auto& floor : solution.floor_results) {
        std::map<Node, std::size_t> route_positions;
        for (std::size_t idx = 0; idx < floor.route.size(); ++idx) route_positions[floor.route[idx]] = idx + 1;
        for (const auto& [loc_idx, qty] : floor.picks) {
            const auto& loc = locs[loc_idx];
            rows.push_back({"PICKER_" + loc.floor,
                            loc.thm_id,
                            loc.article,
                            loc.floor,
                            loc.aisle,
                            loc.column,
                            loc.shelf,
                            loc.side,
                            qty,
                            "PICKCAR_" + loc.floor,
                            route_positions[loc.node()]});
        }
    }
    std::sort(rows.begin(), rows.end(), [](const PickRow& a, const PickRow& b) {
        return std::make_tuple(floor_index(a.floor), a.pick_order, a.aisle, a.column, a.shelf, a.side, a.thm_id, a.article) <
               std::make_tuple(floor_index(b.floor), b.pick_order, b.aisle, b.column, b.shelf, b.side, b.thm_id, b.article);
    });
    std::ofstream file(path);
    file << "PICKER_ID,THM_ID,ARTICLE_CODE,FLOOR,AISLE,COLUMN,SHELF,LEFT_OR_RIGHT,AMOUNT,PICKCAR_ID,PICK_ORDER\n";
    for (const auto& row : rows) {
        file << csv_escape(row.picker_id) << ',' << csv_escape(row.thm_id) << ',' << row.article << ','
             << csv_escape(row.floor) << ',' << row.aisle << ',' << row.column << ',' << row.shelf << ','
             << csv_escape(row.side) << ',' << row.amount << ',' << csv_escape(row.pickcar_id) << ','
             << row.pick_order << '\n';
    }
}

static std::map<std::pair<std::string, Node>, std::string> node_id_map(const std::vector<Loc>& locs) {
    std::set<std::pair<std::string, Node>> keys;
    for (const auto& loc : locs) keys.insert({loc.floor, loc.node()});
    std::vector<std::pair<std::string, Node>> sorted(keys.begin(), keys.end());
    std::sort(sorted.begin(), sorted.end(), [](const auto& a, const auto& b) {
        return std::make_tuple(floor_index(a.first), a.second.aisle, a.second.column) <
               std::make_tuple(floor_index(b.first), b.second.aisle, b.second.column);
    });
    std::map<std::pair<std::string, Node>, std::string> out;
    for (std::size_t idx = 0; idx < sorted.size(); ++idx) {
        std::ostringstream node_id;
        node_id << 'n' << std::setw(5) << std::setfill('0') << idx + 1;
        out[sorted[idx]] = node_id.str();
    }
    return out;
}

static void write_alt_csv(const Solution& solution, const Problem& problem, const fs::path& path) {
    ensure_parent(path);
    std::map<std::size_t, int> picked_qty;
    std::set<std::pair<std::string, Node>> active_nodes;
    std::set<std::string> active_thms;
    std::map<std::pair<std::string, Node>, std::size_t> route_position;
    for (const auto& floor : solution.floor_results) {
        active_thms.insert(floor.opened_thms.begin(), floor.opened_thms.end());
        for (std::size_t idx = 0; idx < floor.route.size(); ++idx) {
            active_nodes.insert({floor.floor, floor.route[idx]});
            route_position[{floor.floor, floor.route[idx]}] = idx + 1;
        }
        for (const auto& [loc_idx, qty] : floor.picks) picked_qty[loc_idx] += qty;
    }
    auto node_ids = node_id_map(problem.locs);

    struct AltRow {
        int article;
        int demand;
        std::string location_id;
        std::string thm_id;
        std::string floor;
        int aisle;
        int column;
        int shelf;
        std::string side;
        int stock;
        std::string node_id;
        bool node_visited;
        bool thm_opened;
        bool selected;
        int picked_amount;
        std::optional<std::size_t> pick_order;
    };
    std::vector<AltRow> rows;
    for (std::size_t idx = 0; idx < problem.locs.size(); ++idx) {
        const auto& loc = problem.locs[idx];
        auto key = std::make_pair(loc.floor, loc.node());
        int picked = picked_qty.count(idx) ? picked_qty[idx] : 0;
        rows.push_back({loc.article,
                        problem.demands.at(loc.article),
                        loc.lid,
                        loc.thm_id,
                        loc.floor,
                        loc.aisle,
                        loc.column,
                        loc.shelf,
                        loc.side,
                        loc.stock,
                        node_ids[key],
                        active_nodes.count(key) > 0,
                        active_thms.count(loc.thm_id) > 0,
                        picked > 0,
                        picked,
                        route_position.count(key) ? std::optional<std::size_t>(route_position[key]) : std::nullopt});
    }
    std::sort(rows.begin(), rows.end(), [](const AltRow& a, const AltRow& b) {
        return std::make_tuple(a.article,
                               !a.selected,
                               a.pick_order.value_or(std::numeric_limits<std::size_t>::max()),
                               floor_index(a.floor),
                               a.aisle,
                               a.column,
                               a.shelf,
                               a.side,
                               a.thm_id,
                               a.location_id) <
               std::make_tuple(b.article,
                               !b.selected,
                               b.pick_order.value_or(std::numeric_limits<std::size_t>::max()),
                               floor_index(b.floor),
                               b.aisle,
                               b.column,
                               b.shelf,
                               b.side,
                               b.thm_id,
                               b.location_id);
    });

    std::ofstream file(path);
    file << "ARTICLE_CODE,ARTICLE_DEMAND,LOCATION_ID,THM_ID,FLOOR,AISLE,COLUMN,SHELF,LEFT_OR_RIGHT,"
            "AVAILABLE_STOCK,NODE_ID,NODE_VISITED,THM_OPENED,IS_SELECTED,PICKED_AMOUNT,PICK_ORDER\n";
    for (const auto& row : rows) {
        file << row.article << ',' << row.demand << ',' << csv_escape(row.location_id) << ','
             << csv_escape(row.thm_id) << ',' << csv_escape(row.floor) << ',' << row.aisle << ','
             << row.column << ',' << row.shelf << ',' << csv_escape(row.side) << ',' << row.stock << ','
             << csv_escape(row.node_id) << ',' << (row.node_visited ? 1 : 0) << ','
             << (row.thm_opened ? 1 : 0) << ',' << (row.selected ? 1 : 0) << ',' << row.picked_amount << ',';
        if (row.pick_order) file << *row.pick_order;
        file << '\n';
    }
}

static void write_summary_json(const Solution& solution, const Args& args, const fs::path& path) {
    ensure_parent(path);
    std::ofstream file(path);
    file << std::fixed << std::setprecision(6);
    file << "{\n";
    file << "  \"algorithm\": " << json_escape(solution.algorithm) << ",\n";
    file << "  \"orders\": " << json_escape(args.orders.string()) << ",\n";
    file << "  \"stock\": " << json_escape(args.stock.string()) << ",\n";
    file << "  \"objective_value\": " << solution.objective << ",\n";
    file << "  \"distance\": " << solution.total_distance << ",\n";
    file << "  \"floors\": " << solution.total_floors << ",\n";
    file << "  \"thms\": " << solution.total_thms << ",\n";
    file << "  \"pick_rows\": " << solution.total_picks << ",\n";
    std::size_t visited_nodes = 0;
    for (const auto& floor : solution.floor_results) visited_nodes += floor.route.size();
    file << "  \"visited_nodes\": " << visited_nodes << ",\n";
    file << "  \"solve_time\": " << solution.solve_time << ",\n";
    file << "  \"notes\": {\n";
    std::size_t idx = 0;
    for (const auto& [key, value] : solution.notes) {
        file << "    " << json_escape(key) << ": " << json_escape(value);
        if (++idx < solution.notes.size()) file << ',';
        file << '\n';
    }
    file << "  }\n";
    file << "}\n";
}

static void print_report(const Solution& solution) {
    std::cout << "\n========================================================================\n";
    std::cout << "  " << upper(solution.algorithm) << " - RESULTS\n";
    std::cout << "========================================================================\n\n";
    std::cout << "  Objective value:            " << std::fixed << std::setprecision(2) << solution.objective << "\n";
    std::cout << "  Total distance:             " << solution.total_distance << " m\n";
    std::cout << "  Active floors:              " << solution.total_floors << "\n";
    std::cout << "  Opened THMs:                " << solution.total_thms << "\n";
    std::cout << "  Pick rows:                  " << solution.total_picks << "\n";
    for (const auto& [key, value] : solution.notes) {
        std::cout << "  " << std::left << std::setw(26) << (key + ":") << value << std::right << "\n";
    }
    std::cout << "\n  Floor details:\n";
    for (const auto& floor : solution.floor_results) {
        std::cout << "    " << floor.floor << ": " << floor.picks.size() << " locations, "
                  << floor.opened_thms.size() << " THMs, " << floor.route.size()
                  << " nodes, distance=" << std::setprecision(1) << floor.route_distance << "m\n";
    }
    std::cout << "\n  Total solve time:           " << std::setprecision(2) << solution.solve_time << " s\n";
    std::cout << "========================================================================\n";
}

static std::optional<std::set<std::string>> parse_floors(const std::string& value) {
    std::set<std::string> floors;
    std::stringstream ss(value);
    std::string token;
    while (std::getline(ss, token, ',')) {
        token = trim(token);
        if (token.empty()) continue;
        auto floor = norm_floor(token);
        if (!floor) throw std::runtime_error("invalid floor filter " + token);
        floors.insert(*floor);
    }
    if (floors.empty()) return std::nullopt;
    return floors;
}

static std::optional<std::set<int>> parse_articles(const std::string& value) {
    std::set<int> articles;
    std::stringstream ss(value);
    std::string token;
    while (std::getline(ss, token, ',')) {
        token = trim(token);
        if (token.empty()) continue;
        articles.insert(std::stoi(token));
    }
    if (articles.empty()) return std::nullopt;
    return articles;
}

static std::string normalize_fallback_method(std::string value) {
    value = upper(trim(value));
    std::replace(value.begin(), value.end(), '_', '-');
    if (value == "GRASP") return "grasp";
    if (value == "VISITED-AREA" || value == "VISITEDAREA" || value == "VISITED" || value == "V2") {
        return "visited-area";
    }
    throw std::runtime_error("invalid --fallback-method, expected grasp or visited-area");
}

static void print_help() {
    std::cout << "C++ current-best warehouse picking heuristic\n\n";
    std::cout << "Options:\n";
    std::cout << "  --orders PATH\n";
    std::cout << "  --stock PATH\n";
    std::cout << "  --time-limit SECONDS              0 means unlimited\n";
    std::cout << "  --fallback-on-time-limit | --no-fallback-on-time-limit\n";
    std::cout << "  --fallback-method grasp|visited-area\n";
    std::cout << "  --cleanup-operator none|2-opt|swap|relocate\n";
    std::cout << "  --cleanup-strategy best|first\n";
    std::cout << "  --floors MZN1,MZN2\n";
    std::cout << "  --articles 88,150,258\n";
    std::cout << "  --output PATH\n";
    std::cout << "  --alternative-locations-output PATH\n";
    std::cout << "  --summary-output PATH\n";
}

static Args parse_args(int argc, char** argv) {
    Args args;
    for (int idx = 1; idx < argc;) {
        std::string flag = argv[idx];
        if (flag == "-h" || flag == "--help") {
            print_help();
            std::exit(0);
        }
        if (flag == "--fallback-on-time-limit") {
            args.fallback_on_time_limit = true;
            ++idx;
            continue;
        }
        if (flag == "--no-fallback-on-time-limit") {
            args.fallback_on_time_limit = false;
            ++idx;
            continue;
        }
        if (idx + 1 >= argc) throw std::runtime_error("missing value for " + flag);
        std::string value = argv[idx + 1];
        if (flag == "--orders") args.orders = value;
        else if (flag == "--stock") args.stock = value;
        else if (flag == "--distance-weight") args.distance_weight = std::stod(value);
        else if (flag == "--thm-weight") args.thm_weight = std::stod(value);
        else if (flag == "--floor-weight") args.floor_weight = std::stod(value);
        else if (flag == "--time-limit") args.time_limit = std::stod(value);
        else if (flag == "--fallback-alpha") args.fallback_alpha = std::stod(value);
        else if (flag == "--fallback-article-rcl-size") args.fallback_article_rcl_size = static_cast<std::size_t>(std::stoull(value));
        else if (flag == "--fallback-location-rcl-size") args.fallback_location_rcl_size = static_cast<std::size_t>(std::stoull(value));
        else if (flag == "--fallback-seed") args.fallback_seed = static_cast<std::uint64_t>(std::stoull(value));
        else if (flag == "--fallback-method") args.fallback_method = normalize_fallback_method(value);
        else if (flag == "--cleanup-operator") args.cleanup_operator = value;
        else if (flag == "--cleanup-strategy") args.cleanup_strategy = value;
        else if (flag == "--cleanup-passes") args.cleanup_passes = static_cast<std::size_t>(std::stoull(value));
        else if (flag == "--floors") args.floors = parse_floors(value);
        else if (flag == "--articles") args.articles = parse_articles(value);
        else if (flag == "--output") args.output = value;
        else if (flag == "--alternative-locations-output") args.alt_output = value;
        else if (flag == "--summary-output") args.summary_output = value;
        else throw std::runtime_error("unknown argument " + flag);
        idx += 2;
    }
    return args;
}

int main(int argc, char** argv) {
    try {
        auto args = parse_args(argc, argv);
        Weights weights{args.distance_weight, args.thm_weight, args.floor_weight};
        auto started = Clock::now();
        std::optional<Clock::time_point> deadline;
        if (args.time_limit > 0.0) deadline = started + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(args.time_limit));

        auto problem = prepare_problem(args.orders, args.stock, args.floors, args.articles);
        auto [solution, notes] = solve_current_best(problem, weights, deadline, args, started);

        auto cleanup_start = Clock::now();
        cleanup_solution_routes(solution, problem.locs, weights, args.cleanup_operator, args.cleanup_strategy, args.cleanup_passes);
        double cleanup_time = std::chrono::duration<double>(Clock::now() - cleanup_start).count();
        solution.solve_time = std::chrono::duration<double>(Clock::now() - started).count();
        notes["route_cleanup"] = args.cleanup_operator + " (" + args.cleanup_strategy + ")";
        std::ostringstream cleanup_time_text;
        cleanup_time_text << std::fixed << std::setprecision(6) << cleanup_time;
        notes["route_cleanup_time"] = cleanup_time_text.str();
        solution.notes = notes;

        write_pick_csv(solution, problem.locs, args.output);
        write_alt_csv(solution, problem, args.alt_output);
        write_summary_json(solution, args, args.summary_output);
        print_report(solution);
        std::cout << "\nPick output written to " << args.output << "\n";
        std::cout << "Alternative locations written to " << args.alt_output << "\n";
        std::cout << "Summary written to " << args.summary_output << "\n";
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << "error: " << exc.what() << "\n";
        return 1;
    }
}

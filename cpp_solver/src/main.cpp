#include "picking_solver/core.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;

struct CliArgs {
    picking_solver::SolverOptions solver;
    fs::path orders = "data/full/PickOrder.csv";
    fs::path stock = "data/full/StockData.csv";
    fs::path output = "outputs/benchmark_outputs/cpp_current_best/current_best_pick.csv";
    fs::path alt_output = "outputs/benchmark_outputs/cpp_current_best/current_best_alt.csv";
    fs::path summary_output = "outputs/benchmark_outputs/cpp_current_best/current_best_summary.json";
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

static std::optional<std::set<std::string>> parse_floors(const std::string& value) {
    static const std::set<std::string> allowed = {"MZN1", "MZN2", "MZN3", "MZN4", "MZN5", "MZN6"};
    std::set<std::string> floors;
    std::stringstream ss(value);
    std::string token;
    while (std::getline(ss, token, ',')) {
        token = upper(trim(token));
        if (token.empty()) continue;
        if (!allowed.count(token)) throw std::runtime_error("invalid floor filter " + token);
        floors.insert(token);
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
        if (!token.empty()) articles.insert(std::stoi(token));
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

static std::string normalize_seed_route_optimizer(std::string value) {
    value = upper(trim(value));
    std::replace(value.begin(), value.end(), '_', '-');
    if (value == "LKH" || value == "LKH-3" || value == "LKH3") return "lkh";
    if (value == "CPP" || value == "C++" || value == "REGRET" || value == "REGRET-2OPT" ||
        value == "REGRET-2-OPT") {
        return "cpp";
    }
    throw std::runtime_error("invalid --seed-route-optimizer, expected lkh or cpp");
}

static std::string normalize_article_selection(std::string value) {
    value = upper(trim(value));
    std::replace(value.begin(), value.end(), '_', '-');
    if (value == "GROUPED") return "grouped";
    if (value == "BUCKET-CHEAPEST" || value == "BUCKETED-CHEAPEST" || value == "BUCKETED" ||
        value == "BUCKET" || value == "GROUP-CHEAPEST" || value == "GROUPED-CHEAPEST") {
        return "bucket-cheapest";
    }
    if (value == "GLOBAL-CHEAPEST" || value == "GLOBAL" || value == "FULL-CHEAPEST" ||
        value == "STRICT-FULL-CHEAPEST" || value == "FULL-STRICT-CHEAPEST") {
        return "global-cheapest";
    }
    throw std::runtime_error("invalid --article-selection, expected grouped, bucket-cheapest, or global-cheapest");
}

static void print_help() {
    std::cout << "C++ current-best warehouse picking heuristic\n\n";
    std::cout << "Options:\n";
    std::cout << "  --orders PATH\n";
    std::cout << "  --stock PATH\n";
    std::cout << "  --time-limit SECONDS              0 means unlimited\n";
    std::cout << "  --fallback-on-time-limit | --no-fallback-on-time-limit\n";
    std::cout << "  --fallback-method grasp|visited-area\n";
    std::cout << "  --seed-route-optimizer lkh|cpp    Seed one-location routes with LKH or C++ regret+2-opt\n";
    std::cout << "  --lkh-path PATH                   Defaults to external/LKH-3.0.14/LKH\n";
    std::cout << "  --lkh-precision N                 Distance scale for LKH integer matrix (default 1000)\n";
    std::cout << "  --lkh-runs N                      LKH runs per seed floor (default 1)\n";
    std::cout << "  --lkh-seed N                      LKH random seed (default 1)\n";
    std::cout << "  --lkh-max-trials N                0 uses max(100, nodes on floor)\n";
    std::cout << "  --article-selection grouped|bucket-cheapest|global-cheapest\n";
    std::cout << "  --candidate-group-width N         Candidate-count bucket width (default 2; 1 restores exact counts)\n";
    std::cout << "  --cleanup-operator none|2-opt|swap|relocate\n";
    std::cout << "  --cleanup-strategy best|first\n";
    std::cout << "  --cleanup-max-time SECONDS        Max time for cleanup (default 120.0)\n";
    std::cout << "  --cleanup-fallback-passes N       Fallback passes when time exceeded (default 3)\n";
    std::cout << "  --floors MZN1,MZN2\n";
    std::cout << "  --articles 88,150,258\n";
    std::cout << "  --output PATH\n";
    std::cout << "  --alternative-locations-output PATH\n";
    std::cout << "  --summary-output PATH\n";
}

static CliArgs parse_args(int argc, char** argv) {
    CliArgs args;
    for (int idx = 1; idx < argc;) {
        std::string flag = argv[idx];
        if (flag == "-h" || flag == "--help") {
            print_help();
            std::exit(0);
        }
        if (flag == "--fallback-on-time-limit") {
            args.solver.fallback_on_time_limit = true;
            ++idx;
            continue;
        }
        if (flag == "--no-fallback-on-time-limit") {
            args.solver.fallback_on_time_limit = false;
            ++idx;
            continue;
        }
        if (idx + 1 >= argc) throw std::runtime_error("missing value for " + flag);
        std::string value = argv[idx + 1];
        if (flag == "--orders") args.orders = value;
        else if (flag == "--stock") args.stock = value;
        else if (flag == "--distance-weight") args.solver.distance_weight = std::stod(value);
        else if (flag == "--thm-weight") args.solver.thm_weight = std::stod(value);
        else if (flag == "--floor-weight") args.solver.floor_weight = std::stod(value);
        else if (flag == "--time-limit") args.solver.time_limit = std::stod(value);
        else if (flag == "--fallback-alpha") args.solver.fallback_alpha = std::stod(value);
        else if (flag == "--fallback-article-rcl-size") {
            args.solver.fallback_article_rcl_size = static_cast<std::size_t>(std::stoull(value));
        } else if (flag == "--fallback-location-rcl-size") {
            args.solver.fallback_location_rcl_size = static_cast<std::size_t>(std::stoull(value));
        } else if (flag == "--fallback-seed") {
            args.solver.fallback_seed = static_cast<std::uint64_t>(std::stoull(value));
        } else if (flag == "--fallback-method") args.solver.fallback_method = normalize_fallback_method(value);
        else if (flag == "--seed-route-optimizer") {
            args.solver.seed_route_optimizer = normalize_seed_route_optimizer(value);
        } else if (flag == "--lkh-path") args.solver.lkh_path = value;
        else if (flag == "--lkh-precision") args.solver.lkh_precision = std::stoi(value);
        else if (flag == "--lkh-runs") args.solver.lkh_runs = std::stoi(value);
        else if (flag == "--lkh-seed") args.solver.lkh_seed = std::stoi(value);
        else if (flag == "--lkh-max-trials") args.solver.lkh_max_trials = std::stoi(value);
        else if (flag == "--article-selection") {
            args.solver.article_selection = normalize_article_selection(value);
        } else if (flag == "--candidate-group-width") {
            args.solver.candidate_group_width =
                std::max<std::size_t>(1, static_cast<std::size_t>(std::stoull(value)));
        } else if (flag == "--cleanup-operator") args.solver.cleanup_operator = value;
        else if (flag == "--cleanup-strategy") args.solver.cleanup_strategy = value;
        else if (flag == "--cleanup-passes") {
            args.solver.cleanup_passes = static_cast<std::size_t>(std::stoull(value));
        } else if (flag == "--cleanup-max-time") args.solver.cleanup_max_time = std::stod(value);
        else if (flag == "--cleanup-fallback-passes") {
            args.solver.cleanup_fallback_passes = static_cast<std::size_t>(std::stoull(value));
        } else if (flag == "--floors") args.solver.floors = parse_floors(value);
        else if (flag == "--articles") args.solver.articles = parse_articles(value);
        else if (flag == "--output") args.output = value;
        else if (flag == "--alternative-locations-output") args.alt_output = value;
        else if (flag == "--summary-output") args.summary_output = value;
        else throw std::runtime_error("unknown argument " + flag);
        idx += 2;
    }
    args.solver.orders_label = args.orders.string();
    args.solver.stock_label = args.stock.string();
    return args;
}

static std::string read_text(const fs::path& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error("failed to read " + path.string());
    std::ostringstream text;
    text << file.rdbuf();
    return text.str();
}

static void write_text(const fs::path& path, const std::string& text) {
    if (path.has_parent_path()) fs::create_directories(path.parent_path());
    std::ofstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error("failed to write " + path.string());
    file << text;
}

int main(int argc, char** argv) {
    try {
        auto args = parse_args(argc, argv);
        auto artifacts = picking_solver::solve_csv(read_text(args.orders), read_text(args.stock), args.solver);
        write_text(args.output, artifacts.pick_csv);
        write_text(args.alt_output, artifacts.alternative_locations_csv);
        write_text(args.summary_output, artifacts.summary_json);
        std::cout << artifacts.report;
        std::cout << "\nPick output written to " << args.output << "\n";
        std::cout << "Alternative locations written to " << args.alt_output << "\n";
        std::cout << "Summary written to " << args.summary_output << "\n";
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << "error: " << exc.what() << "\n";
        return 1;
    }
}

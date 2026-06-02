#include "picking_solver/core.hpp"

#include <emscripten/bind.h>

#include <algorithm>
#include <cctype>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

struct WasmSolverOptions {
    std::string orders_label = "orders.csv";
    std::string stock_label = "stock.csv";
    double distance_weight = 1.0;
    double thm_weight = 15.0;
    double floor_weight = 30.0;
    double time_limit = 120.0;
    bool fallback_on_time_limit = true;
    double fallback_alpha = 0.25;
    unsigned fallback_article_rcl_size = 6;
    unsigned fallback_location_rcl_size = 5;
    unsigned fallback_seed = 7;
    std::string fallback_method = "grasp";
    int lkh_precision = 1000;
    int lkh_runs = 1;
    int lkh_seed = 1;
    int lkh_max_trials = 0;
    unsigned candidate_group_width = 2;
    std::string article_selection = "grouped";
    std::string cleanup_operator = "2-opt";
    std::string cleanup_strategy = "best";
    unsigned cleanup_passes = 3;
    double cleanup_max_time = 120.0;
    unsigned cleanup_fallback_passes = 3;
    std::string floors_csv;
    std::string articles_csv;
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

static picking_solver::SolverOptions make_solver_options(const WasmSolverOptions& wasm_options) {
    picking_solver::SolverOptions options;
    options.orders_label = wasm_options.orders_label;
    options.stock_label = wasm_options.stock_label;
    options.distance_weight = wasm_options.distance_weight;
    options.thm_weight = wasm_options.thm_weight;
    options.floor_weight = wasm_options.floor_weight;
    options.time_limit = wasm_options.time_limit;
    options.fallback_on_time_limit = wasm_options.fallback_on_time_limit;
    options.fallback_alpha = wasm_options.fallback_alpha;
    options.fallback_article_rcl_size = wasm_options.fallback_article_rcl_size;
    options.fallback_location_rcl_size = wasm_options.fallback_location_rcl_size;
    options.fallback_seed = wasm_options.fallback_seed;
    options.fallback_method = wasm_options.fallback_method;
    options.lkh_precision = std::max(1, wasm_options.lkh_precision);
    options.lkh_runs = std::max(1, wasm_options.lkh_runs);
    options.lkh_seed = wasm_options.lkh_seed;
    options.lkh_max_trials = std::max(0, wasm_options.lkh_max_trials);
    options.candidate_group_width = std::max(1U, wasm_options.candidate_group_width);
    options.article_selection = wasm_options.article_selection;
    options.cleanup_operator = wasm_options.cleanup_operator;
    options.cleanup_strategy = wasm_options.cleanup_strategy;
    options.cleanup_passes = wasm_options.cleanup_passes;
    options.cleanup_max_time = wasm_options.cleanup_max_time;
    options.cleanup_fallback_passes = wasm_options.cleanup_fallback_passes;
    options.floors = parse_floors(wasm_options.floors_csv);
    options.articles = parse_articles(wasm_options.articles_csv);
    return options;
}

static picking_solver::SolverArtifacts solve_csv_lkh_free(
    const std::string& orders_csv,
    const std::string& stock_csv,
    const WasmSolverOptions& wasm_options
) {
    auto options = make_solver_options(wasm_options);
    options.seed_route_optimizer = "cpp";
    return picking_solver::solve_csv(orders_csv, stock_csv, options);
}

static picking_solver::SolverArtifacts solve_csv_with_lkh_runner(
    const std::string& orders_csv,
    const std::string& stock_csv,
    const WasmSolverOptions& wasm_options,
    emscripten::val lkh_runner
) {
    auto options = make_solver_options(wasm_options);
    options.seed_route_optimizer = "lkh";
    options.lkh_tour_runner = [lkh_runner](const std::string& floor,
                                          const std::string& tsp_text,
                                          const std::string& par_text) {
        return lkh_runner(floor, tsp_text, par_text).as<std::string>();
    };
    return picking_solver::solve_csv(orders_csv, stock_csv, options);
}

}  // namespace

EMSCRIPTEN_BINDINGS(picking_solver_wasm) {
    emscripten::value_object<WasmSolverOptions>("WasmSolverOptions")
        .field("ordersLabel", &WasmSolverOptions::orders_label)
        .field("stockLabel", &WasmSolverOptions::stock_label)
        .field("distanceWeight", &WasmSolverOptions::distance_weight)
        .field("thmWeight", &WasmSolverOptions::thm_weight)
        .field("floorWeight", &WasmSolverOptions::floor_weight)
        .field("timeLimit", &WasmSolverOptions::time_limit)
        .field("fallbackOnTimeLimit", &WasmSolverOptions::fallback_on_time_limit)
        .field("fallbackAlpha", &WasmSolverOptions::fallback_alpha)
        .field("fallbackArticleRclSize", &WasmSolverOptions::fallback_article_rcl_size)
        .field("fallbackLocationRclSize", &WasmSolverOptions::fallback_location_rcl_size)
        .field("fallbackSeed", &WasmSolverOptions::fallback_seed)
        .field("fallbackMethod", &WasmSolverOptions::fallback_method)
        .field("lkhPrecision", &WasmSolverOptions::lkh_precision)
        .field("lkhRuns", &WasmSolverOptions::lkh_runs)
        .field("lkhSeed", &WasmSolverOptions::lkh_seed)
        .field("lkhMaxTrials", &WasmSolverOptions::lkh_max_trials)
        .field("candidateGroupWidth", &WasmSolverOptions::candidate_group_width)
        .field("articleSelection", &WasmSolverOptions::article_selection)
        .field("cleanupOperator", &WasmSolverOptions::cleanup_operator)
        .field("cleanupStrategy", &WasmSolverOptions::cleanup_strategy)
        .field("cleanupPasses", &WasmSolverOptions::cleanup_passes)
        .field("cleanupMaxTime", &WasmSolverOptions::cleanup_max_time)
        .field("cleanupFallbackPasses", &WasmSolverOptions::cleanup_fallback_passes)
        .field("floorsCsv", &WasmSolverOptions::floors_csv)
        .field("articlesCsv", &WasmSolverOptions::articles_csv);

    emscripten::value_object<picking_solver::SolverArtifacts>("SolverArtifacts")
        .field("pickCsv", &picking_solver::SolverArtifacts::pick_csv)
        .field("alternativeLocationsCsv", &picking_solver::SolverArtifacts::alternative_locations_csv)
        .field("summaryJson", &picking_solver::SolverArtifacts::summary_json)
        .field("report", &picking_solver::SolverArtifacts::report);

    emscripten::function("solveCsvLkhFree", &solve_csv_lkh_free);
    emscripten::function("solveCsvWithLkhRunner", &solve_csv_with_lkh_runner);
}

#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <optional>
#include <set>
#include <string>

namespace picking_solver {

using LkhTourRunner = std::function<std::string(
    const std::string& floor,
    const std::string& tsp_text,
    const std::string& par_text
)>;

struct SolverOptions {
    std::string orders_label = "orders.csv";
    std::string stock_label = "stock.csv";
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
    std::string seed_route_optimizer = "lkh";
    std::string lkh_path;
    int lkh_precision = 1000;
    int lkh_runs = 1;
    int lkh_seed = 1;
    int lkh_max_trials = 0;
    LkhTourRunner lkh_tour_runner;
    std::size_t candidate_group_width = 2;
    std::string article_selection = "grouped";
    std::string cleanup_operator = "2-opt";
    std::string cleanup_strategy = "best";
    std::size_t cleanup_passes = 3;
    double cleanup_max_time = 120.0;
    std::size_t cleanup_fallback_passes = 3;
    std::optional<std::set<std::string>> floors;
    std::optional<std::set<int>> articles;
};

struct SolverArtifacts {
    std::string pick_csv;
    std::string alternative_locations_csv;
    std::string summary_json;
    std::string report;
};

SolverArtifacts solve_csv(
    const std::string& orders_csv,
    const std::string& stock_csv,
    const SolverOptions& options
);

}  // namespace picking_solver

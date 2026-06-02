#include "picking_solver/core.hpp"

#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

static std::string read_text(const std::string& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error("failed to read " + path);
    std::ostringstream text;
    text << file.rdbuf();
    return text.str();
}

static void require_contains(const std::string& text, const std::string& expected) {
    if (text.find(expected) == std::string::npos) {
        throw std::runtime_error("expected output to contain: " + expected);
    }
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("expected orders and stock CSV paths");

        picking_solver::SolverOptions options;
        options.orders_label = argv[1];
        options.stock_label = argv[2];
        options.articles = std::set<int>{567, 577, 606, 609, 699};
        options.time_limit = 20.0;
        options.seed_route_optimizer = "cpp";
        options.article_selection = "grouped";
        options.candidate_group_width = 2;
        options.fallback_method = "grasp";
        options.cleanup_operator = "2-opt";
        options.cleanup_strategy = "best";
        options.cleanup_passes = 3;

        auto artifacts = picking_solver::solve_csv(read_text(argv[1]), read_text(argv[2]), options);
        require_contains(artifacts.pick_csv, "PICKER_ID,THM_ID,ARTICLE_CODE");
        require_contains(artifacts.alternative_locations_csv, "ARTICLE_CODE,ARTICLE_DEMAND,LOCATION_ID");
        require_contains(artifacts.summary_json, "\"objective_value\": 312.740000");
        require_contains(artifacts.summary_json, "\"distance\": 207.740000");
        require_contains(artifacts.summary_json, "\"thms\": 5");
        require_contains(artifacts.summary_json, "\"pick_rows\": 5");
        require_contains(artifacts.summary_json, "\"seed_route_optimizer\": \"cpp\"");
        require_contains(artifacts.summary_json, "pure C++ regret insertion + 2-opt (LKH not used)");

        std::cout << "core API smoke passed\n";
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << "error: " << exc.what() << "\n";
        return 1;
    }
}

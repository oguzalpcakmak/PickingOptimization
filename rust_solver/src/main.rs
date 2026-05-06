use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::env;
use std::fs;
use std::hash::{Hash, Hasher};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

const AISLE_WIDTH: f64 = 1.36;
const COLUMN_LENGTH: f64 = 2.90;
const SHELF_DEPTH: f64 = 1.16;
const CROSS_AISLE_WIDTH: f64 = 2.70;
const TOTAL_AISLES: i32 = 27;
const TOTAL_COLUMNS: i32 = 20;
const AISLE_PITCH: f64 = AISLE_WIDTH + (2.0 * SHELF_DEPTH);
const CROSS_AISLE_CENTERS: [f64; 3] = [
    CROSS_AISLE_WIDTH / 2.0,
    CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH + (CROSS_AISLE_WIDTH / 2.0),
    CROSS_AISLE_WIDTH
        + 10.0 * COLUMN_LENGTH
        + CROSS_AISLE_WIDTH
        + 10.0 * COLUMN_LENGTH
        + (CROSS_AISLE_WIDTH / 2.0),
];

const FLOOR_ORDER: [&str; 6] = ["MZN1", "MZN2", "MZN3", "MZN4", "MZN5", "MZN6"];
const EPS: f64 = 1e-9;

type AppResult<T> = Result<T, String>;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
struct Node {
    aisle: i32,
    column: i32,
}

#[derive(Debug, Clone)]
struct Loc {
    lid: String,
    thm_id: String,
    article: i32,
    floor: String,
    aisle: i32,
    side: String,
    column: i32,
    shelf: i32,
    stock: i32,
}

impl Loc {
    fn node(&self) -> Node {
        Node {
            aisle: self.aisle,
            column: self.column,
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct Weights {
    distance: f64,
    thm: f64,
    floor: f64,
}

#[derive(Debug, Clone)]
struct Candidate {
    loc_idx: usize,
    take: i32,
    unit_cost: f64,
    marginal_cost: f64,
    route_delta: f64,
    insert_index: Option<usize>,
    new_floor: bool,
    new_thm: bool,
    new_node: bool,
    route_nodes: Option<Vec<Node>>,
    route_total_cost: Option<f64>,
}

#[derive(Debug, Clone)]
struct FloorResult {
    floor: String,
    picks: BTreeMap<usize, i32>,
    route: Vec<Node>,
    route_distance: f64,
    opened_thms: BTreeSet<String>,
}

#[derive(Debug, Clone)]
struct Solution {
    algorithm: String,
    floor_results: Vec<FloorResult>,
    total_distance: f64,
    total_thms: usize,
    total_floors: usize,
    total_picks: usize,
    solve_time: f64,
    objective: f64,
    notes: BTreeMap<String, String>,
}

#[derive(Debug)]
struct Problem {
    demands: BTreeMap<i32, i32>,
    locs: Vec<Loc>,
    article_to_candidates: BTreeMap<i32, Vec<usize>>,
}

#[derive(Debug)]
struct State {
    remaining_stock: Vec<i32>,
    picks_by_location: BTreeMap<usize, i32>,
    picks_by_article: BTreeMap<i32, BTreeMap<usize, i32>>,
    active_floors: BTreeSet<String>,
    active_thms: BTreeSet<String>,
    active_nodes_by_floor: BTreeMap<String, BTreeSet<Node>>,
    route_by_floor: BTreeMap<String, Vec<Node>>,
    route_cost_by_floor: BTreeMap<String, f64>,
}

impl State {
    fn new(locs: &[Loc]) -> Self {
        Self {
            remaining_stock: locs.iter().map(|loc| loc.stock).collect(),
            picks_by_location: BTreeMap::new(),
            picks_by_article: BTreeMap::new(),
            active_floors: BTreeSet::new(),
            active_thms: BTreeSet::new(),
            active_nodes_by_floor: BTreeMap::new(),
            route_by_floor: BTreeMap::new(),
            route_cost_by_floor: BTreeMap::new(),
        }
    }

    fn picked_for_article(&self, article: i32) -> i32 {
        self.picks_by_article
            .get(&article)
            .map(|picks| picks.values().sum())
            .unwrap_or(0)
    }

    fn remaining_demand(&self, demands: &BTreeMap<i32, i32>, article: i32) -> i32 {
        demands
            .get(&article)
            .map(|demand| (demand - self.picked_for_article(article)).max(0))
            .unwrap_or(0)
    }

    fn evaluate_candidate(
        &self,
        locs: &[Loc],
        weights: Weights,
        loc_idx: usize,
        remaining_demand: i32,
    ) -> Option<Candidate> {
        let loc = &locs[loc_idx];
        let available = self.remaining_stock[loc_idx];
        if available <= 0 || remaining_demand <= 0 {
            return None;
        }

        let take = available.min(remaining_demand);
        let new_floor = !self.active_floors.contains(&loc.floor);
        let new_thm = !self.active_thms.contains(&loc.thm_id);
        let node = loc.node();
        let new_node = !self
            .active_nodes_by_floor
            .get(&loc.floor)
            .map(|nodes| nodes.contains(&node))
            .unwrap_or(false);

        let (route_delta, insert_index) = if new_node {
            let route = self
                .route_by_floor
                .get(&loc.floor)
                .map(Vec::as_slice)
                .unwrap_or(&[]);
            best_insertion(route, node)
        } else {
            let len = self
                .route_by_floor
                .get(&loc.floor)
                .map(|route| route.len())
                .unwrap_or(0);
            (0.0, len)
        };

        let marginal_cost = (weights.distance * route_delta)
            + if new_thm { weights.thm } else { 0.0 }
            + if new_floor { weights.floor } else { 0.0 };
        Some(Candidate {
            loc_idx,
            take,
            unit_cost: marginal_cost / take.max(1) as f64,
            marginal_cost,
            route_delta,
            insert_index: Some(insert_index),
            new_floor,
            new_thm,
            new_node,
            route_nodes: None,
            route_total_cost: None,
        })
    }

    fn evaluate_candidate_strict(
        &self,
        locs: &[Loc],
        weights: Weights,
        loc_idx: usize,
        remaining_demand: i32,
    ) -> Option<Candidate> {
        let loc = &locs[loc_idx];
        let available = self.remaining_stock[loc_idx];
        if available <= 0 || remaining_demand <= 0 {
            return None;
        }

        let take = available.min(remaining_demand);
        let new_floor = !self.active_floors.contains(&loc.floor);
        let new_thm = !self.active_thms.contains(&loc.thm_id);
        let node = loc.node();
        let new_node = !self
            .active_nodes_by_floor
            .get(&loc.floor)
            .map(|nodes| nodes.contains(&node))
            .unwrap_or(false);

        let mut insert_index = self
            .route_by_floor
            .get(&loc.floor)
            .map(|route| route.len())
            .unwrap_or(0);
        let mut route_delta = 0.0;
        let mut route_nodes = None;
        let mut route_total_cost = None;
        if new_node {
            let route = self
                .route_by_floor
                .get(&loc.floor)
                .map(Vec::as_slice)
                .unwrap_or(&[]);
            let current_cost = *self.route_cost_by_floor.get(&loc.floor).unwrap_or(&0.0);
            let (total, index, new_route) = strict_best_position_cost(route, node);
            insert_index = index;
            route_delta = total - current_cost;
            route_nodes = Some(new_route);
            route_total_cost = Some(total);
        }

        let marginal_cost = (weights.distance * route_delta)
            + if new_thm { weights.thm } else { 0.0 }
            + if new_floor { weights.floor } else { 0.0 };
        Some(Candidate {
            loc_idx,
            take,
            unit_cost: marginal_cost / take.max(1) as f64,
            marginal_cost,
            route_delta,
            insert_index: Some(insert_index),
            new_floor,
            new_thm,
            new_node,
            route_nodes,
            route_total_cost,
        })
    }

    fn commit(&mut self, locs: &[Loc], candidate: &Candidate) -> AppResult<()> {
        let loc = &locs[candidate.loc_idx];
        let available = self.remaining_stock[candidate.loc_idx];
        if candidate.take <= 0 || candidate.take > available {
            return Err(format!(
                "invalid commit for {}: requested {}, available {}",
                loc.lid, candidate.take, available
            ));
        }

        self.remaining_stock[candidate.loc_idx] -= candidate.take;
        *self.picks_by_location.entry(candidate.loc_idx).or_insert(0) += candidate.take;
        *self
            .picks_by_article
            .entry(loc.article)
            .or_default()
            .entry(candidate.loc_idx)
            .or_insert(0) += candidate.take;

        if candidate.new_floor {
            self.active_floors.insert(loc.floor.clone());
        }
        if candidate.new_thm {
            self.active_thms.insert(loc.thm_id.clone());
        }
        if candidate.new_node {
            if let Some(route_nodes) = &candidate.route_nodes {
                self.route_by_floor
                    .insert(loc.floor.clone(), route_nodes.clone());
                self.route_cost_by_floor.insert(
                    loc.floor.clone(),
                    candidate
                        .route_total_cost
                        .unwrap_or_else(|| route_cost(route_nodes)),
                );
            } else {
                let route = self.route_by_floor.entry(loc.floor.clone()).or_default();
                let index = candidate
                    .insert_index
                    .ok_or_else(|| format!("missing insertion index for {}", loc.lid))?;
                route.insert(index, loc.node());
                *self
                    .route_cost_by_floor
                    .entry(loc.floor.clone())
                    .or_insert(0.0) += candidate.route_delta;
            }
            self.active_nodes_by_floor
                .entry(loc.floor.clone())
                .or_default()
                .insert(loc.node());
        }
        Ok(())
    }
}

#[derive(Debug, Clone)]
struct Args {
    orders: PathBuf,
    stock: PathBuf,
    distance_weight: f64,
    thm_weight: f64,
    floor_weight: f64,
    time_limit: f64,
    fallback_on_time_limit: bool,
    fallback_alpha: f64,
    fallback_article_rcl_size: usize,
    fallback_location_rcl_size: usize,
    fallback_seed: u64,
    cleanup_operator: String,
    cleanup_strategy: String,
    cleanup_passes: usize,
    floors: Option<BTreeSet<String>>,
    articles: Option<BTreeSet<i32>>,
    output: PathBuf,
    alt_output: PathBuf,
    summary_output: PathBuf,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("error: {err}");
        std::process::exit(1);
    }
}

fn run() -> AppResult<()> {
    let args = parse_args()?;
    let weights = Weights {
        distance: args.distance_weight,
        thm: args.thm_weight,
        floor: args.floor_weight,
    };
    let started = Instant::now();
    let deadline = if args.time_limit > 0.0 {
        Some(started + Duration::from_secs_f64(args.time_limit))
    } else {
        None
    };

    let problem = prepare_problem(&args.orders, &args.stock, &args.floors, &args.articles)?;
    let (mut solution, mut notes) =
        solve_current_best(&problem, weights, deadline, &args, started)?;
    let cleanup_start = Instant::now();
    cleanup_solution_routes(
        &mut solution,
        &problem.locs,
        weights,
        &args.cleanup_operator,
        &args.cleanup_strategy,
        args.cleanup_passes,
    )?;
    let cleanup_time = cleanup_start.elapsed().as_secs_f64();
    solution.solve_time = started.elapsed().as_secs_f64();
    notes.insert(
        "route_cleanup".to_string(),
        format!("{} ({})", args.cleanup_operator, args.cleanup_strategy),
    );
    notes.insert(
        "route_cleanup_time".to_string(),
        format!("{cleanup_time:.6}"),
    );
    solution.notes = notes;

    write_pick_csv(&solution, &problem.locs, &args.output)?;
    write_alt_csv(&solution, &problem, &args.alt_output)?;
    write_summary_json(&solution, &args, &args.summary_output)?;
    print_report(&solution);
    println!("\nPick output written to {}", args.output.display());
    println!(
        "Alternative locations written to {}",
        args.alt_output.display()
    );
    println!("Summary written to {}", args.summary_output.display());
    Ok(())
}

fn solve_current_best(
    problem: &Problem,
    weights: Weights,
    deadline: Option<Instant>,
    args: &Args,
    started: Instant,
) -> AppResult<(Solution, BTreeMap<String, String>)> {
    let prep_start = Instant::now();
    let mut state = State::new(&problem.locs);
    let mut counts: BTreeMap<i32, usize> = BTreeMap::new();
    for (article, candidates) in &problem.article_to_candidates {
        counts.insert(*article, candidates.len());
    }

    for (article, count) in &counts {
        if *count != 1 {
            continue;
        }
        let loc_idx = problem.article_to_candidates[article][0];
        let mut remaining = *problem.demands.get(article).unwrap_or(&0);
        while remaining > 0 {
            let candidate = state
                .evaluate_candidate(&problem.locs, weights, loc_idx, remaining)
                .ok_or_else(|| {
                    format!("article {article} has no feasible single-location stock")
                })?;
            remaining -= candidate.take;
            state.commit(&problem.locs, &candidate)?;
        }
    }
    let prep_elapsed = prep_start.elapsed().as_secs_f64();

    // Pure Rust seed replacement for Python's external LK package.
    let seed_start = Instant::now();
    let floors: Vec<String> = state.active_nodes_by_floor.keys().cloned().collect();
    for floor in floors {
        let nodes = state
            .active_nodes_by_floor
            .get(&floor)
            .cloned()
            .unwrap_or_default();
        let mut route = build_route(nodes.iter().copied(), true);
        route = two_opt_route(&route, 3);
        let cost = route_cost(&route);
        state.route_by_floor.insert(floor.clone(), route);
        state.route_cost_by_floor.insert(floor, cost);
    }
    let seed_elapsed = seed_start.elapsed().as_secs_f64();

    let grouped_start = Instant::now();
    let mut timed_out = false;
    let mut timeout_group = 0usize;
    let mut timeout_article = 0i32;
    let mut fast_reuse_steps = 0usize;
    let mut strict_steps = 0usize;
    let mut strict_candidate_evals = 0usize;
    let mut strict_position_evals = 0usize;

    let mut groups: BTreeMap<usize, Vec<i32>> = BTreeMap::new();
    for (article, count) in &counts {
        if *count >= 2 {
            groups.entry(*count).or_default().push(*article);
        }
    }

    'groups: for (group_size, articles) in groups {
        for article in articles {
            let mut remaining = state.remaining_demand(&problem.demands, article);
            while remaining > 0 {
                if deadline
                    .map(|deadline| Instant::now() >= deadline)
                    .unwrap_or(false)
                {
                    timed_out = true;
                    timeout_group = group_size;
                    timeout_article = article;
                    break 'groups;
                }

                let candidates = problem
                    .article_to_candidates
                    .get(&article)
                    .ok_or_else(|| format!("missing candidates for article {article}"))?;
                let feasible: Vec<usize> = candidates
                    .iter()
                    .copied()
                    .filter(|idx| state.remaining_stock[*idx] > 0)
                    .collect();
                let open_thm_locs: Vec<usize> = feasible
                    .iter()
                    .copied()
                    .filter(|idx| state.active_thms.contains(&problem.locs[*idx].thm_id))
                    .collect();

                if !open_thm_locs.is_empty() {
                    let mut scored: Vec<Candidate> = open_thm_locs
                        .into_iter()
                        .filter_map(|idx| {
                            state.evaluate_candidate(&problem.locs, weights, idx, remaining)
                        })
                        .collect();
                    scored.sort_by(|a, b| candidate_cmp(a, b, &problem.locs));
                    let best = scored
                        .first()
                        .ok_or_else(|| {
                            format!("article {article} has no open-THM feasible candidate")
                        })?
                        .clone();
                    remaining -= best.take;
                    state.commit(&problem.locs, &best)?;
                    fast_reuse_steps += 1;
                    continue;
                }

                let mut scored = Vec::new();
                for idx in feasible {
                    strict_candidate_evals += 1;
                    let loc = &problem.locs[idx];
                    let route_len = state
                        .route_by_floor
                        .get(&loc.floor)
                        .map(|route| route.len())
                        .unwrap_or(0);
                    let is_new_node = !state
                        .active_nodes_by_floor
                        .get(&loc.floor)
                        .map(|nodes| nodes.contains(&loc.node()))
                        .unwrap_or(false);
                    if is_new_node {
                        strict_position_evals += route_len + 1;
                    }
                    if let Some(candidate) =
                        state.evaluate_candidate_strict(&problem.locs, weights, idx, remaining)
                    {
                        scored.push(candidate);
                    }
                }
                if scored.is_empty() {
                    return Err(format!(
                        "article {article} still has demand {remaining}, but no feasible stock remains"
                    ));
                }
                scored.sort_by(|a, b| candidate_cmp(a, b, &problem.locs));
                let best = scored[0].clone();
                remaining -= best.take;
                state.commit(&problem.locs, &best)?;
                strict_steps += 1;
            }
        }
    }

    let remaining_before_fallback: BTreeMap<i32, i32> = problem
        .demands
        .keys()
        .filter_map(|article| {
            let remaining = state.remaining_demand(&problem.demands, *article);
            if remaining > 0 {
                Some((*article, remaining))
            } else {
                None
            }
        })
        .collect();

    let mut fallback_articles = 0usize;
    let mut fallback_steps = 0usize;
    let mut fallback_candidate_evals = 0usize;
    if timed_out && args.fallback_on_time_limit {
        let fallback = complete_with_grasp_fallback(
            &mut state,
            problem,
            weights,
            args.fallback_alpha,
            args.fallback_article_rcl_size,
            args.fallback_location_rcl_size,
            args.fallback_seed,
        )?;
        fallback_articles = fallback.0;
        fallback_steps = fallback.1;
        fallback_candidate_evals = fallback.2;
    }

    let construction_time = started.elapsed().as_secs_f64();
    let mut notes = BTreeMap::new();
    notes.insert(
        "seed_route".to_string(),
        "pure Rust regret insertion + 2-opt (LK package not used)".to_string(),
    );
    notes.insert("time_limit_sec".to_string(), format!("{}", args.time_limit));
    notes.insert("timed_out".to_string(), timed_out.to_string());
    notes.insert("timeout_group".to_string(), timeout_group.to_string());
    notes.insert("timeout_article".to_string(), timeout_article.to_string());
    notes.insert(
        "fallback_on_time_limit".to_string(),
        args.fallback_on_time_limit.to_string(),
    );
    notes.insert(
        "fallback_used".to_string(),
        (timed_out && args.fallback_on_time_limit).to_string(),
    );
    notes.insert(
        "remaining_articles_before_fallback".to_string(),
        remaining_before_fallback.len().to_string(),
    );
    notes.insert(
        "remaining_units_before_fallback".to_string(),
        remaining_before_fallback.values().sum::<i32>().to_string(),
    );
    notes.insert("fast_reuse_steps".to_string(), fast_reuse_steps.to_string());
    notes.insert("strict_steps".to_string(), strict_steps.to_string());
    notes.insert(
        "strict_candidate_evals".to_string(),
        strict_candidate_evals.to_string(),
    );
    notes.insert(
        "strict_position_evals".to_string(),
        strict_position_evals.to_string(),
    );
    notes.insert(
        "fallback_articles".to_string(),
        fallback_articles.to_string(),
    );
    notes.insert("fallback_steps".to_string(), fallback_steps.to_string());
    notes.insert(
        "fallback_candidate_evals".to_string(),
        fallback_candidate_evals.to_string(),
    );
    notes.insert(
        "prep_single_location_sec".to_string(),
        format!("{prep_elapsed:.6}"),
    );
    notes.insert("seed_route_sec".to_string(), format!("{seed_elapsed:.6}"));
    notes.insert(
        "ascending_grouped_phase_sec".to_string(),
        format!("{:.6}", grouped_start.elapsed().as_secs_f64()),
    );

    let solution = build_solution_from_state(
        "Rust current-best: grouped insertion + open THM shortcut + GRASP fallback".to_string(),
        problem,
        &state,
        weights,
        construction_time,
    );
    Ok((solution, notes))
}

fn complete_with_grasp_fallback(
    state: &mut State,
    problem: &Problem,
    weights: Weights,
    alpha: f64,
    article_rcl_size: usize,
    location_rcl_size: usize,
    seed: u64,
) -> AppResult<(usize, usize, usize)> {
    let mut rng = SimpleRng::new(seed);
    let remaining_demands: BTreeMap<i32, i32> = problem
        .demands
        .keys()
        .filter_map(|article| {
            let remaining = state.remaining_demand(&problem.demands, *article);
            if remaining > 0 {
                Some((*article, remaining))
            } else {
                None
            }
        })
        .collect();
    let mut remaining_articles = compute_article_order(&remaining_demands, problem, weights)?;
    let mut steps = 0usize;
    let mut candidate_evals = 0usize;
    let mut articles_completed = 0usize;

    while !remaining_articles.is_empty() {
        let limit = article_rcl_size.max(1).min(remaining_articles.len());
        let article_index = rng.randrange(limit);
        let article = remaining_articles.remove(article_index);

        loop {
            let remaining = state.remaining_demand(&problem.demands, article);
            if remaining <= 0 {
                break;
            }
            let mut scored = Vec::new();
            for loc_idx in problem
                .article_to_candidates
                .get(&article)
                .ok_or_else(|| format!("missing candidates for article {article}"))?
            {
                candidate_evals += 1;
                if let Some(candidate) =
                    state.evaluate_candidate(&problem.locs, weights, *loc_idx, remaining)
                {
                    scored.push(candidate);
                }
            }
            if scored.is_empty() {
                return Err(format!(
                    "article {article} still has demand {remaining}, but no feasible stock remains"
                ));
            }
            scored.sort_by(|a, b| candidate_cmp(a, b, &problem.locs));
            let rcl = build_rcl(&scored, alpha, location_rcl_size);
            let chosen = weighted_choice(&rcl, &mut rng).clone();
            state.commit(&problem.locs, &chosen)?;
            steps += 1;
        }
        articles_completed += 1;
    }

    Ok((articles_completed, steps, candidate_evals))
}

fn build_solution_from_state(
    algorithm: String,
    problem: &Problem,
    state: &State,
    weights: Weights,
    solve_time: f64,
) -> Solution {
    let mut picks_by_floor: BTreeMap<String, BTreeMap<usize, i32>> = BTreeMap::new();
    let mut active_nodes_by_floor: BTreeMap<String, BTreeSet<Node>> = BTreeMap::new();
    for (loc_idx, qty) in &state.picks_by_location {
        if *qty <= 0 {
            continue;
        }
        let loc = &problem.locs[*loc_idx];
        picks_by_floor
            .entry(loc.floor.clone())
            .or_default()
            .insert(*loc_idx, *qty);
        active_nodes_by_floor
            .entry(loc.floor.clone())
            .or_default()
            .insert(loc.node());
    }

    let mut floor_results = Vec::new();
    for floor in sort_floors(picks_by_floor.keys().cloned().collect()) {
        let picks = picks_by_floor.remove(&floor).unwrap_or_default();
        let nodes = active_nodes_by_floor.remove(&floor).unwrap_or_default();
        let mut route = if nodes.len() <= 60 {
            build_route(nodes.iter().copied(), true)
        } else {
            seed_route_from_hint(
                &nodes,
                state
                    .route_by_floor
                    .get(&floor)
                    .map(Vec::as_slice)
                    .unwrap_or(&[]),
            )
        };
        if route.is_empty() && !nodes.is_empty() {
            route = build_route(nodes.iter().copied(), true);
        }
        let route_distance = route_cost(&route);
        let opened_thms = picks
            .keys()
            .map(|idx| problem.locs[*idx].thm_id.clone())
            .collect::<BTreeSet<_>>();
        floor_results.push(FloorResult {
            floor,
            picks,
            route,
            route_distance,
            opened_thms,
        });
    }

    let all_thms = floor_results
        .iter()
        .flat_map(|floor| floor.opened_thms.iter().cloned())
        .collect::<BTreeSet<_>>();
    let total_distance: f64 = floor_results.iter().map(|floor| floor.route_distance).sum();
    let total_picks = floor_results.iter().map(|floor| floor.picks.len()).sum();
    let total_floors = floor_results.len();
    let total_thms = all_thms.len();
    let objective = weights.distance * total_distance
        + weights.thm * total_thms as f64
        + weights.floor * total_floors as f64;

    Solution {
        algorithm,
        floor_results,
        total_distance,
        total_thms,
        total_floors,
        total_picks,
        solve_time,
        objective,
        notes: BTreeMap::new(),
    }
}

fn cleanup_solution_routes(
    solution: &mut Solution,
    locs: &[Loc],
    weights: Weights,
    operator: &str,
    strategy: &str,
    max_passes: usize,
) -> AppResult<()> {
    for floor in &mut solution.floor_results {
        floor.route = cleanup_route_delta(&floor.route, operator, strategy, max_passes)?;
        floor.route_distance = route_cost(&floor.route);
    }
    let all_thms = solution
        .floor_results
        .iter()
        .flat_map(|floor| floor.opened_thms.iter().cloned())
        .collect::<BTreeSet<_>>();
    solution.total_distance = solution
        .floor_results
        .iter()
        .map(|floor| floor.route_distance)
        .sum();
    solution.total_floors = solution.floor_results.len();
    solution.total_thms = all_thms.len();
    solution.total_picks = solution
        .floor_results
        .iter()
        .map(|floor| floor.picks.len())
        .sum();
    solution.objective = weights.distance * solution.total_distance
        + weights.thm * solution.total_thms as f64
        + weights.floor * solution.total_floors as f64;
    solution.algorithm = format!(
        "{}, {} cleanup ({})",
        solution.algorithm, operator, strategy
    );

    // Validate route positions before writing outputs.
    for floor in &solution.floor_results {
        let route_nodes: HashSet<Node> = floor.route.iter().copied().collect();
        for loc_idx in floor.picks.keys() {
            let node = locs[*loc_idx].node();
            if !route_nodes.contains(&node) {
                return Err(format!(
                    "route for {} misses selected node {:?}",
                    floor.floor, node
                ));
            }
        }
    }
    Ok(())
}

fn cleanup_route_delta(
    route: &[Node],
    operator: &str,
    strategy: &str,
    max_passes: usize,
) -> AppResult<Vec<Node>> {
    let normalized = operator.to_ascii_lowercase().replace('_', "-");
    if normalized == "none" || normalized == "noop" || normalized == "no-op" {
        return Ok(route.to_vec());
    }
    if strategy != "first" && strategy != "best" {
        return Err(format!("unsupported cleanup strategy '{strategy}'"));
    }
    let op = if normalized == "two-opt" || normalized == "2opt" || normalized == "2-opt" {
        "2-opt"
    } else if normalized == "swap" {
        "swap"
    } else if normalized == "relocate" {
        "relocate"
    } else {
        return Err(format!("unsupported cleanup operator '{operator}'"));
    };

    let mut improved = route.to_vec();
    if improved.len() <= 1 || (op == "2-opt" && improved.len() <= 2) {
        return Ok(improved);
    }

    for _ in 0..max_passes {
        let mut best_move: Option<(f64, usize, usize)> = None;
        let mut applied = false;

        match op {
            "2-opt" => {
                for left in 0..improved.len() - 1 {
                    for right in left + 1..improved.len() {
                        let delta = two_opt_delta(&improved, left, right);
                        if delta < -EPS {
                            if strategy == "first" {
                                improved[left..=right].reverse();
                                applied = true;
                                break;
                            }
                            if best_move.map(|m| delta < m.0 - 1e-12).unwrap_or(true) {
                                best_move = Some((delta, left, right));
                            }
                        }
                    }
                    if applied {
                        break;
                    }
                }
                if strategy == "best" {
                    if let Some((_, left, right)) = best_move {
                        improved[left..=right].reverse();
                        applied = true;
                    }
                }
            }
            "swap" => {
                for left in 0..improved.len() - 1 {
                    for right in left + 1..improved.len() {
                        let delta = swap_delta(&improved, left, right);
                        if delta < -EPS {
                            if strategy == "first" {
                                improved.swap(left, right);
                                applied = true;
                                break;
                            }
                            if best_move.map(|m| delta < m.0 - 1e-12).unwrap_or(true) {
                                best_move = Some((delta, left, right));
                            }
                        }
                    }
                    if applied {
                        break;
                    }
                }
                if strategy == "best" {
                    if let Some((_, left, right)) = best_move {
                        improved.swap(left, right);
                        applied = true;
                    }
                }
            }
            "relocate" => {
                for source in 0..improved.len() {
                    for target in 0..improved.len() {
                        if target == source {
                            continue;
                        }
                        let delta = relocate_delta(&improved, source, target);
                        if delta < -EPS {
                            if strategy == "first" {
                                let node = improved.remove(source);
                                improved.insert(target, node);
                                applied = true;
                                break;
                            }
                            if best_move.map(|m| delta < m.0 - 1e-12).unwrap_or(true) {
                                best_move = Some((delta, source, target));
                            }
                        }
                    }
                    if applied {
                        break;
                    }
                }
                if strategy == "best" {
                    if let Some((_, source, target)) = best_move {
                        let node = improved.remove(source);
                        improved.insert(target, node);
                        applied = true;
                    }
                }
            }
            _ => unreachable!(),
        }
        if !applied {
            break;
        }
    }
    Ok(improved)
}

fn prepare_problem(
    orders: &Path,
    stock: &Path,
    floor_filter: &Option<BTreeSet<String>>,
    article_filter: &Option<BTreeSet<i32>>,
) -> AppResult<Problem> {
    let mut demands = load_demands(orders)?;
    if let Some(articles) = article_filter {
        demands.retain(|article, _| articles.contains(article));
    }
    if demands.is_empty() {
        return Err("no demanded articles after filters".to_string());
    }

    let all_locs = load_stock(stock)?;
    let mut locs = Vec::new();
    for loc in all_locs {
        if !demands.contains_key(&loc.article) {
            continue;
        }
        if floor_filter
            .as_ref()
            .map(|floors| !floors.contains(&loc.floor))
            .unwrap_or(false)
        {
            continue;
        }
        locs.push(loc);
    }

    let mut article_to_candidates: BTreeMap<i32, Vec<usize>> = BTreeMap::new();
    let mut stock_by_article: BTreeMap<i32, i32> = BTreeMap::new();
    for (idx, loc) in locs.iter().enumerate() {
        article_to_candidates
            .entry(loc.article)
            .or_default()
            .push(idx);
        *stock_by_article.entry(loc.article).or_insert(0) += loc.stock;
    }

    for article in demands.keys() {
        if !article_to_candidates.contains_key(article) {
            return Err(format!(
                "no stock rows found for demanded article {article}"
            ));
        }
        let available = *stock_by_article.get(article).unwrap_or(&0);
        let demand = *demands.get(article).unwrap_or(&0);
        if available < demand {
            return Err(format!(
                "insufficient stock for article {article}: demand={demand}, available={available}"
            ));
        }
    }

    for candidates in article_to_candidates.values_mut() {
        candidates.sort_by(|a, b| loc_cmp(&locs[*a], &locs[*b]));
    }

    Ok(Problem {
        demands,
        locs,
        article_to_candidates,
    })
}

fn load_demands(path: &Path) -> AppResult<BTreeMap<i32, i32>> {
    let rows = read_csv(path, ',')?;
    let mut demands = BTreeMap::new();
    for row in rows {
        let Some(article) = row.get("ARTICLE_CODE").and_then(|v| parse_i32(v)) else {
            continue;
        };
        let Some(amount) = row.get("AMOUNT").and_then(|v| parse_i32(v)) else {
            continue;
        };
        if amount < 0 {
            return Err(format!("negative demand for article {article}"));
        }
        *demands.entry(article).or_insert(0) += amount;
    }
    Ok(demands)
}

fn load_stock(path: &Path) -> AppResult<Vec<Loc>> {
    let rows = read_csv(path, ',')?;
    let mut aggregated: BTreeMap<(String, i32, String, i32, String, i32, i32), i32> =
        BTreeMap::new();
    for row in rows {
        let Some(article) = row.get("ARTICLE_CODE").and_then(|v| parse_i32(v)) else {
            continue;
        };
        let Some(aisle) = row.get("AISLE").and_then(|v| parse_i32(v)) else {
            continue;
        };
        let Some(column) = row.get("COLUMN").and_then(|v| parse_i32(v)) else {
            continue;
        };
        let Some(shelf) = row.get("SHELF").and_then(|v| parse_i32(v)) else {
            continue;
        };
        let stock = row
            .get("STOCK")
            .or_else(|| row.get("STOCK_AMOUNT"))
            .and_then(|v| parse_i32(v));
        let Some(stock) = stock else {
            continue;
        };
        let Some(floor) = row.get("FLOOR").and_then(|v| norm_floor(v)) else {
            continue;
        };
        let side_raw = row
            .get("RIGHT_OR_LEFT")
            .or_else(|| row.get("LEFT_OR_RIGHT"))
            .map(String::as_str)
            .unwrap_or("");
        let Some(side) = norm_side(side_raw) else {
            continue;
        };
        let thm_id = row
            .get("THM_ID")
            .map(|v| v.trim().to_string())
            .unwrap_or_default();
        if thm_id.is_empty() || stock <= 0 {
            continue;
        }
        if !(1..=TOTAL_AISLES).contains(&aisle) || !(1..=TOTAL_COLUMNS).contains(&column) {
            continue;
        }
        *aggregated
            .entry((thm_id, article, floor, aisle, side, column, shelf))
            .or_insert(0) += stock;
    }

    let mut locs = Vec::new();
    for (index, ((thm_id, article, floor, aisle, side, column, shelf), stock)) in
        aggregated.into_iter().enumerate()
    {
        locs.push(Loc {
            lid: format!("j{:05}", index + 1),
            thm_id,
            article,
            floor,
            aisle,
            side,
            column,
            shelf,
            stock,
        });
    }
    Ok(locs)
}

fn read_csv(path: &Path, delimiter: char) -> AppResult<Vec<HashMap<String, String>>> {
    let text = fs::read_to_string(path)
        .map_err(|err| format!("failed to read {}: {err}", path.display()))?;
    let text = text.trim_start_matches('\u{feff}');
    let mut lines = text.lines();
    let header_line = lines
        .next()
        .ok_or_else(|| format!("{} is empty", path.display()))?
        .trim_end_matches('\r');
    let headers = parse_csv_line(header_line, delimiter);
    let mut rows = Vec::new();
    for line in lines {
        let line = line.trim_end_matches('\r');
        if line.trim().is_empty() {
            continue;
        }
        let values = parse_csv_line(line, delimiter);
        let mut row = HashMap::new();
        for (idx, header) in headers.iter().enumerate() {
            row.insert(header.clone(), values.get(idx).cloned().unwrap_or_default());
        }
        rows.push(row);
    }
    Ok(rows)
}

fn parse_csv_line(line: &str, delimiter: char) -> Vec<String> {
    let mut out = Vec::new();
    let mut field = String::new();
    let mut chars = line.chars().peekable();
    let mut in_quotes = false;
    while let Some(ch) = chars.next() {
        if ch == '"' {
            if in_quotes && chars.peek() == Some(&'"') {
                field.push('"');
                chars.next();
            } else {
                in_quotes = !in_quotes;
            }
        } else if ch == delimiter && !in_quotes {
            out.push(field.trim().to_string());
            field.clear();
        } else {
            field.push(ch);
        }
    }
    out.push(field.trim().to_string());
    out
}

fn parse_i32(value: &str) -> Option<i32> {
    let text = value.trim();
    if text.is_empty() {
        return None;
    }
    text.parse::<i32>()
        .ok()
        .or_else(|| text.parse::<f64>().ok().map(|value| value as i32))
}

fn norm_floor(value: &str) -> Option<String> {
    let floor = value.trim().to_ascii_uppercase();
    if FLOOR_ORDER.contains(&floor.as_str()) {
        Some(floor)
    } else {
        None
    }
}

fn norm_side(value: &str) -> Option<String> {
    let side = value.trim().to_ascii_uppercase();
    if side.starts_with('L') {
        Some("L".to_string())
    } else if side.starts_with('R') {
        Some("R".to_string())
    } else {
        None
    }
}

fn floor_index(floor: &str) -> usize {
    FLOOR_ORDER
        .iter()
        .position(|item| *item == floor)
        .map(|idx| idx + 1)
        .unwrap_or(999)
}

fn sort_floors(mut floors: Vec<String>) -> Vec<String> {
    floors.sort_by_key(|floor| floor_index(floor));
    floors
}

fn reversed_aisle(aisle: i32) -> i32 {
    TOTAL_AISLES - aisle + 1
}

fn x_coord(aisle: i32) -> f64 {
    (SHELF_DEPTH + AISLE_WIDTH / 2.0) + ((reversed_aisle(aisle) - 1) as f64 * AISLE_PITCH)
}

fn y_coord(column: i32) -> f64 {
    if column <= 10 {
        CROSS_AISLE_WIDTH + ((column as f64 - 0.5) * COLUMN_LENGTH)
    } else {
        CROSS_AISLE_WIDTH
            + 10.0 * COLUMN_LENGTH
            + CROSS_AISLE_WIDTH
            + ((column as f64 - 10.0 - 0.5) * COLUMN_LENGTH)
    }
}

fn same_floor_distance(a: Node, b: Node) -> f64 {
    let x1 = x_coord(a.aisle);
    let y1 = y_coord(a.column);
    let x2 = x_coord(b.aisle);
    let y2 = y_coord(b.column);
    if a.aisle == b.aisle {
        return (y1 - y2).abs();
    }
    CROSS_AISLE_CENTERS
        .iter()
        .map(|cross_y| (y1 - cross_y).abs() + (x1 - x2).abs() + (cross_y - y2).abs())
        .fold(f64::INFINITY, f64::min)
}

fn stair_position(stair_id: i32) -> (f64, f64) {
    let (a1, a2, cross) = match stair_id {
        1 => (5, 6, 1),
        2 => (15, 16, 1),
        3 => (24, 25, 1),
        4 => (9, 10, 2),
        5 => (19, 20, 2),
        6 => (4, 5, 3),
        7 => (14, 15, 3),
        8 => (23, 24, 3),
        _ => (5, 6, 1),
    };
    let x = (x_coord(a1) + x_coord(a2)) / 2.0;
    let y = match cross {
        1 => CROSS_AISLE_WIDTH,
        2 => CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH,
        _ => CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + 10.0 * COLUMN_LENGTH,
    };
    (x, y)
}

fn nearest_elevator(aisle: i32) -> i32 {
    if (aisle - 8).abs() <= (aisle - 18).abs() {
        1
    } else {
        2
    }
}

fn elevator_aisle(elevator: i32) -> i32 {
    if elevator == 1 { 8 } else { 18 }
}

fn nearest_stair_to_elevator(elevator: i32) -> i32 {
    let elevator_x = x_coord(elevator_aisle(elevator));
    let mut best_id = 1;
    let mut best_distance = f64::INFINITY;
    for stair_id in [1, 2, 3] {
        let (stair_x, _) = stair_position(stair_id);
        let distance = (stair_x - elevator_x).abs();
        if distance < best_distance {
            best_distance = distance;
            best_id = stair_id;
        }
    }
    best_id
}

fn entry_exit_distance(node: Node) -> f64 {
    let elevator = nearest_elevator(node.aisle);
    let stair = nearest_stair_to_elevator(elevator);
    let (stair_x, _) = stair_position(stair);
    let elevator_x = x_coord(elevator_aisle(elevator));
    let stair_to_elevator = (stair_x - elevator_x).abs() + CROSS_AISLE_WIDTH;
    let mut elevator_to_pick = (node.aisle - elevator_aisle(elevator)).abs() as f64 * AISLE_PITCH;
    elevator_to_pick += if node.column <= 10 {
        CROSS_AISLE_WIDTH + ((node.column as f64 - 0.5) * COLUMN_LENGTH)
    } else {
        CROSS_AISLE_WIDTH
            + 10.0 * COLUMN_LENGTH
            + CROSS_AISLE_WIDTH
            + ((node.column as f64 - 10.0 - 0.5) * COLUMN_LENGTH)
    };
    stair_to_elevator + elevator_to_pick
}

fn route_cost(route: &[Node]) -> f64 {
    if route.is_empty() {
        return 0.0;
    }
    let mut total = entry_exit_distance(route[0]);
    for idx in 0..route.len() - 1 {
        total += same_floor_distance(route[idx], route[idx + 1]);
    }
    total + entry_exit_distance(route[route.len() - 1])
}

fn edge_cost(left: Option<Node>, right: Option<Node>) -> f64 {
    match (left, right) {
        (None, None) => 0.0,
        (None, Some(node)) | (Some(node), None) => entry_exit_distance(node),
        (Some(a), Some(b)) => same_floor_distance(a, b),
    }
}

fn insertion_options(route: &[Node], node: Node) -> Vec<(f64, usize)> {
    if route.is_empty() {
        return vec![(2.0 * entry_exit_distance(node), 0)];
    }
    let mut options = Vec::with_capacity(route.len() + 1);
    options.push((
        entry_exit_distance(node) + same_floor_distance(node, route[0])
            - entry_exit_distance(route[0]),
        0,
    ));
    for idx in 0..route.len() - 1 {
        options.push((
            same_floor_distance(route[idx], node) + same_floor_distance(node, route[idx + 1])
                - same_floor_distance(route[idx], route[idx + 1]),
            idx + 1,
        ));
    }
    options.push((
        same_floor_distance(route[route.len() - 1], node) + entry_exit_distance(node)
            - entry_exit_distance(route[route.len() - 1]),
        route.len(),
    ));
    options.sort_by(|a, b| cmp_f64(a.0, b.0).then_with(|| a.1.cmp(&b.1)));
    options
}

fn best_insertion(route: &[Node], node: Node) -> (f64, usize) {
    insertion_options(route, node)[0]
}

fn strict_best_position_cost(route: &[Node], node: Node) -> (f64, usize, Vec<Node>) {
    if route.is_empty() {
        return (route_cost(&[node]), 0, vec![node]);
    }
    let mut best_total = f64::INFINITY;
    let mut best_index = 0usize;
    let mut best_route = Vec::new();
    for index in 0..=route.len() {
        let mut trial = route.to_vec();
        trial.insert(index, node);
        let total = route_cost(&trial);
        if total < best_total - 1e-12 || ((total - best_total).abs() <= 1e-12 && index < best_index)
        {
            best_total = total;
            best_index = index;
            best_route = trial;
        }
    }
    (best_total, best_index, best_route)
}

fn build_route<I: IntoIterator<Item = Node>>(nodes: I, use_regret: bool) -> Vec<Node> {
    let mut unique: BTreeSet<Node> = nodes.into_iter().collect();
    if unique.len() <= 1 {
        return unique.into_iter().collect();
    }
    let seed = *unique
        .iter()
        .max_by(|a, b| {
            cmp_f64(entry_exit_distance(**a), entry_exit_distance(**b))
                .then_with(|| b.aisle.cmp(&a.aisle))
                .then_with(|| b.column.cmp(&a.column))
        })
        .unwrap();
    let mut route = vec![seed];
    unique.remove(&seed);

    while !unique.is_empty() {
        let mut evaluated: Vec<(f64, f64, Node, usize)> = Vec::new();
        for node in &unique {
            let options = insertion_options(&route, *node);
            let (best_delta, best_index) = options[0];
            let second_delta = options.get(1).map(|item| item.0).unwrap_or(best_delta);
            let regret = second_delta - best_delta;
            evaluated.push((regret, best_delta, *node, best_index));
        }
        evaluated.sort_by(|a, b| {
            if use_regret {
                cmp_f64(-a.0, -b.0)
                    .then_with(|| cmp_f64(a.1, b.1))
                    .then_with(|| a.2.aisle.cmp(&b.2.aisle))
                    .then_with(|| a.2.column.cmp(&b.2.column))
            } else {
                cmp_f64(a.1, b.1)
                    .then_with(|| cmp_f64(-a.0, -b.0))
                    .then_with(|| a.2.aisle.cmp(&b.2.aisle))
                    .then_with(|| a.2.column.cmp(&b.2.column))
            }
        });
        let (_, _, chosen, index) = evaluated[0];
        route.insert(index, chosen);
        unique.remove(&chosen);
    }
    route
}

fn two_opt_route(route: &[Node], max_passes: usize) -> Vec<Node> {
    let mut best = route.to_vec();
    if best.len() <= 2 {
        return best;
    }
    for _ in 0..max_passes {
        let mut improved = false;
        for i in 0..best.len() - 1 {
            let prev = if i > 0 { Some(best[i - 1]) } else { None };
            for j in i + 1..best.len() {
                let next = if j + 1 < best.len() {
                    Some(best[j + 1])
                } else {
                    None
                };
                let old_cost = edge_cost(prev, Some(best[i])) + edge_cost(Some(best[j]), next);
                let new_cost = edge_cost(prev, Some(best[j])) + edge_cost(Some(best[i]), next);
                if new_cost + EPS < old_cost {
                    best[i..=j].reverse();
                    improved = true;
                }
            }
        }
        if !improved {
            break;
        }
    }
    best
}

fn node_at(route: &[Node], index: isize) -> Option<Node> {
    if index < 0 || index as usize >= route.len() {
        None
    } else {
        Some(route[index as usize])
    }
}

fn node_after_swap(route: &[Node], index: isize, left: usize, right: usize) -> Option<Node> {
    if index < 0 || index as usize >= route.len() {
        return None;
    }
    let idx = index as usize;
    if idx == left {
        Some(route[right])
    } else if idx == right {
        Some(route[left])
    } else {
        Some(route[idx])
    }
}

fn two_opt_delta(route: &[Node], left: usize, right: usize) -> f64 {
    let prev = node_at(route, left as isize - 1);
    let next = node_at(route, right as isize + 1);
    edge_cost(prev, Some(route[right])) + edge_cost(Some(route[left]), next)
        - edge_cost(prev, Some(route[left]))
        - edge_cost(Some(route[right]), next)
}

fn swap_delta(route: &[Node], left: usize, right: usize) -> f64 {
    let edges = [
        left as isize - 1,
        left as isize,
        right as isize - 1,
        right as isize,
    ];
    let mut seen = BTreeSet::new();
    let mut old_cost = 0.0;
    let mut new_cost = 0.0;
    for edge_left in edges {
        if !seen.insert(edge_left) {
            continue;
        }
        if edge_left < -1 || edge_left as usize >= route.len() {
            continue;
        }
        old_cost += edge_cost(node_at(route, edge_left), node_at(route, edge_left + 1));
        new_cost += edge_cost(
            node_after_swap(route, edge_left, left, right),
            node_after_swap(route, edge_left + 1, left, right),
        );
    }
    new_cost - old_cost
}

fn relocate_delta(route: &[Node], source: usize, target: usize) -> f64 {
    let node = route[source];
    let prev = node_at(route, source as isize - 1);
    let next = node_at(route, source as isize + 1);
    let removal = edge_cost(prev, next) - edge_cost(prev, Some(node)) - edge_cost(Some(node), next);
    let mut without = route.to_vec();
    without.remove(source);
    let prev_insert = if target > 0 {
        Some(without[target - 1])
    } else {
        None
    };
    let next_insert = if target < without.len() {
        Some(without[target])
    } else {
        None
    };
    let insert = edge_cost(prev_insert, Some(node)) + edge_cost(Some(node), next_insert)
        - edge_cost(prev_insert, next_insert);
    removal + insert
}

fn seed_route_from_hint(nodes: &BTreeSet<Node>, hint: &[Node]) -> Vec<Node> {
    let mut route = Vec::new();
    let mut seen = BTreeSet::new();
    for node in hint {
        if nodes.contains(node) && seen.insert(*node) {
            route.push(*node);
        }
    }
    for node in nodes {
        if seen.insert(*node) {
            let (_, index) = best_insertion(&route, *node);
            route.insert(index, *node);
        }
    }
    route
}

fn compute_article_order(
    remaining: &BTreeMap<i32, i32>,
    problem: &Problem,
    weights: Weights,
) -> AppResult<Vec<i32>> {
    let mut ranked: Vec<(ArticleRank, i32)> = Vec::new();
    for (article, demand) in remaining {
        let candidates = problem
            .article_to_candidates
            .get(article)
            .ok_or_else(|| format!("article {article} has demand but no candidate locations"))?;
        let total_stock: i32 = candidates.iter().map(|idx| problem.locs[*idx].stock).sum();
        let floors = candidates
            .iter()
            .map(|idx| problem.locs[*idx].floor.clone())
            .collect::<BTreeSet<_>>();
        let nodes = candidates
            .iter()
            .map(|idx| {
                let loc = &problem.locs[*idx];
                (loc.floor.clone(), loc.aisle, loc.column)
            })
            .collect::<BTreeSet<_>>();
        let mut base_scores = Vec::new();
        for idx in candidates {
            let loc = &problem.locs[*idx];
            let take = (*demand).min(loc.stock).max(1);
            let base_cost = weights.distance * (2.0 * entry_exit_distance(loc.node()))
                + weights.thm
                + weights.floor;
            base_scores.push((
                base_cost / take as f64,
                base_cost,
                -take,
                floor_index(&loc.floor),
                loc.aisle,
                loc.column,
                loc.shelf,
                loc.thm_id.clone(),
                loc.lid.clone(),
            ));
        }
        base_scores.sort_by(|a, b| {
            cmp_f64(a.0, b.0)
                .then_with(|| cmp_f64(a.1, b.1))
                .then_with(|| a.2.cmp(&b.2))
                .then_with(|| a.3.cmp(&b.3))
                .then_with(|| a.4.cmp(&b.4))
                .then_with(|| a.5.cmp(&b.5))
                .then_with(|| a.6.cmp(&b.6))
                .then_with(|| a.7.cmp(&b.7))
                .then_with(|| a.8.cmp(&b.8))
        });
        let regret_rank = if base_scores.len() == 1 {
            -1e18
        } else {
            -0.0_f64.max(base_scores[1].0 - base_scores[0].0)
        };
        ranked.push((
            ArticleRank {
                candidate_count: candidates.len(),
                floor_count: floors.len(),
                regret_rank,
                node_count: nodes.len(),
                slack: total_stock - demand,
                neg_demand: -*demand,
                article: *article,
            },
            *article,
        ));
    }
    ranked.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(ranked.into_iter().map(|(_, article)| article).collect())
}

#[derive(Debug, Clone, Copy)]
struct ArticleRank {
    candidate_count: usize,
    floor_count: usize,
    regret_rank: f64,
    node_count: usize,
    slack: i32,
    neg_demand: i32,
    article: i32,
}

impl Eq for ArticleRank {}

impl PartialEq for ArticleRank {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other) == Ordering::Equal
    }
}

impl PartialOrd for ArticleRank {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for ArticleRank {
    fn cmp(&self, other: &Self) -> Ordering {
        self.candidate_count
            .cmp(&other.candidate_count)
            .then_with(|| self.floor_count.cmp(&other.floor_count))
            .then_with(|| cmp_f64(self.regret_rank, other.regret_rank))
            .then_with(|| self.node_count.cmp(&other.node_count))
            .then_with(|| self.slack.cmp(&other.slack))
            .then_with(|| self.neg_demand.cmp(&other.neg_demand))
            .then_with(|| self.article.cmp(&other.article))
    }
}

fn build_rcl(scored: &[Candidate], alpha: f64, max_size: usize) -> Vec<Candidate> {
    if scored.is_empty() {
        return Vec::new();
    }
    let limit = max_size.max(1).min(scored.len());
    let prefix = &scored[..limit];
    let best = prefix[0].unit_cost;
    let worst = prefix[prefix.len() - 1].unit_cost;
    if (best - worst).abs() <= 1e-12 {
        return prefix.to_vec();
    }
    let threshold = best + alpha.clamp(0.0, 1.0) * (worst - best);
    let rcl: Vec<Candidate> = prefix
        .iter()
        .filter(|candidate| candidate.unit_cost <= threshold + 1e-12)
        .cloned()
        .collect();
    if rcl.is_empty() {
        vec![prefix[0].clone()]
    } else {
        rcl
    }
}

fn weighted_choice<'a>(rcl: &'a [Candidate], rng: &mut SimpleRng) -> &'a Candidate {
    if rcl.len() == 1 {
        return &rcl[0];
    }
    let total: usize = (1..=rcl.len()).sum();
    let mut draw = rng.randrange(total);
    for (idx, candidate) in rcl.iter().enumerate() {
        let weight = rcl.len() - idx;
        if draw < weight {
            return candidate;
        }
        draw -= weight;
    }
    &rcl[0]
}

fn candidate_cmp(a: &Candidate, b: &Candidate, locs: &[Loc]) -> Ordering {
    let la = &locs[a.loc_idx];
    let lb = &locs[b.loc_idx];
    cmp_f64(a.unit_cost, b.unit_cost)
        .then_with(|| cmp_f64(a.marginal_cost, b.marginal_cost))
        .then_with(|| a.new_floor.cmp(&b.new_floor))
        .then_with(|| a.new_thm.cmp(&b.new_thm))
        .then_with(|| a.new_node.cmp(&b.new_node))
        .then_with(|| cmp_f64(a.route_delta, b.route_delta))
        .then_with(|| (-a.take).cmp(&(-b.take)))
        .then_with(|| floor_index(&la.floor).cmp(&floor_index(&lb.floor)))
        .then_with(|| la.aisle.cmp(&lb.aisle))
        .then_with(|| la.column.cmp(&lb.column))
        .then_with(|| la.shelf.cmp(&lb.shelf))
        .then_with(|| la.side.cmp(&lb.side))
        .then_with(|| la.thm_id.cmp(&lb.thm_id))
        .then_with(|| la.lid.cmp(&lb.lid))
}

fn loc_cmp(a: &Loc, b: &Loc) -> Ordering {
    floor_index(&a.floor)
        .cmp(&floor_index(&b.floor))
        .then_with(|| a.aisle.cmp(&b.aisle))
        .then_with(|| a.column.cmp(&b.column))
        .then_with(|| a.shelf.cmp(&b.shelf))
        .then_with(|| a.side.cmp(&b.side))
        .then_with(|| a.thm_id.cmp(&b.thm_id))
        .then_with(|| a.lid.cmp(&b.lid))
}

fn cmp_f64(a: f64, b: f64) -> Ordering {
    a.partial_cmp(&b).unwrap_or(Ordering::Equal)
}

#[derive(Clone)]
struct SimpleRng {
    state: u64,
}

impl SimpleRng {
    fn new(seed: u64) -> Self {
        Self {
            state: if seed == 0 {
                0x9e37_79b9_7f4a_7c15
            } else {
                seed
            },
        }
    }

    fn next_u64(&mut self) -> u64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.state
    }

    fn randrange(&mut self, upper: usize) -> usize {
        if upper <= 1 {
            0
        } else {
            (self.next_u64() as usize) % upper
        }
    }
}

fn write_pick_csv(solution: &Solution, locs: &[Loc], path: &Path) -> AppResult<()> {
    ensure_parent(path)?;
    let mut rows = Vec::new();
    for floor in &solution.floor_results {
        let route_positions: BTreeMap<Node, usize> = floor
            .route
            .iter()
            .enumerate()
            .map(|(idx, node)| (*node, idx + 1))
            .collect();
        for (loc_idx, qty) in &floor.picks {
            let loc = &locs[*loc_idx];
            let pick_order = route_positions.get(&loc.node()).copied().unwrap_or(0);
            rows.push(PickRow {
                picker_id: format!("PICKER_{}", loc.floor),
                thm_id: loc.thm_id.clone(),
                article: loc.article,
                floor: loc.floor.clone(),
                aisle: loc.aisle,
                column: loc.column,
                shelf: loc.shelf,
                side: loc.side.clone(),
                amount: *qty,
                pickcar_id: format!("PICKCAR_{}", loc.floor),
                pick_order,
            });
        }
    }
    rows.sort_by(|a, b| {
        floor_index(&a.floor)
            .cmp(&floor_index(&b.floor))
            .then_with(|| a.pick_order.cmp(&b.pick_order))
            .then_with(|| a.aisle.cmp(&b.aisle))
            .then_with(|| a.column.cmp(&b.column))
            .then_with(|| a.shelf.cmp(&b.shelf))
            .then_with(|| a.side.cmp(&b.side))
            .then_with(|| a.thm_id.cmp(&b.thm_id))
            .then_with(|| a.article.cmp(&b.article))
    });

    let mut file = fs::File::create(path)
        .map_err(|err| format!("failed to create {}: {err}", path.display()))?;
    writeln!(
        file,
        "PICKER_ID,THM_ID,ARTICLE_CODE,FLOOR,AISLE,COLUMN,SHELF,LEFT_OR_RIGHT,AMOUNT,PICKCAR_ID,PICK_ORDER"
    )
    .map_err(|err| err.to_string())?;
    for row in rows {
        writeln!(
            file,
            "{},{},{},{},{},{},{},{},{},{},{}",
            csv_escape(&row.picker_id),
            csv_escape(&row.thm_id),
            row.article,
            csv_escape(&row.floor),
            row.aisle,
            row.column,
            row.shelf,
            csv_escape(&row.side),
            row.amount,
            csv_escape(&row.pickcar_id),
            row.pick_order
        )
        .map_err(|err| err.to_string())?;
    }
    Ok(())
}

#[derive(Debug)]
struct PickRow {
    picker_id: String,
    thm_id: String,
    article: i32,
    floor: String,
    aisle: i32,
    column: i32,
    shelf: i32,
    side: String,
    amount: i32,
    pickcar_id: String,
    pick_order: usize,
}

fn write_alt_csv(solution: &Solution, problem: &Problem, path: &Path) -> AppResult<()> {
    ensure_parent(path)?;
    let mut picked_qty: BTreeMap<usize, i32> = BTreeMap::new();
    let mut active_nodes: BTreeSet<(String, Node)> = BTreeSet::new();
    let mut active_thms: BTreeSet<String> = BTreeSet::new();
    let mut route_position: BTreeMap<(String, Node), usize> = BTreeMap::new();

    for floor in &solution.floor_results {
        active_thms.extend(floor.opened_thms.iter().cloned());
        for (idx, node) in floor.route.iter().enumerate() {
            active_nodes.insert((floor.floor.clone(), *node));
            route_position.insert((floor.floor.clone(), *node), idx + 1);
        }
        for (loc_idx, qty) in &floor.picks {
            *picked_qty.entry(*loc_idx).or_insert(0) += *qty;
        }
    }

    let node_id_map = node_id_map(&problem.locs);
    let mut rows: Vec<AltRow> = Vec::new();
    for (idx, loc) in problem.locs.iter().enumerate() {
        let node = loc.node();
        let key = (loc.floor.clone(), node);
        let picked = *picked_qty.get(&idx).unwrap_or(&0);
        rows.push(AltRow {
            article: loc.article,
            demand: *problem.demands.get(&loc.article).unwrap_or(&0),
            location_id: loc.lid.clone(),
            thm_id: loc.thm_id.clone(),
            floor: loc.floor.clone(),
            aisle: loc.aisle,
            column: loc.column,
            shelf: loc.shelf,
            side: loc.side.clone(),
            stock: loc.stock,
            node_id: node_id_map.get(&key).cloned().unwrap_or_default(),
            node_visited: active_nodes.contains(&key),
            thm_opened: active_thms.contains(&loc.thm_id),
            selected: picked > 0,
            picked_amount: picked,
            pick_order: route_position.get(&key).copied(),
        });
    }
    rows.sort_by(|a, b| {
        a.article
            .cmp(&b.article)
            .then_with(|| b.selected.cmp(&a.selected))
            .then_with(|| {
                a.pick_order
                    .unwrap_or(usize::MAX)
                    .cmp(&b.pick_order.unwrap_or(usize::MAX))
            })
            .then_with(|| floor_index(&a.floor).cmp(&floor_index(&b.floor)))
            .then_with(|| a.aisle.cmp(&b.aisle))
            .then_with(|| a.column.cmp(&b.column))
            .then_with(|| a.shelf.cmp(&b.shelf))
            .then_with(|| a.side.cmp(&b.side))
            .then_with(|| a.thm_id.cmp(&b.thm_id))
            .then_with(|| a.location_id.cmp(&b.location_id))
    });

    let mut file = fs::File::create(path)
        .map_err(|err| format!("failed to create {}: {err}", path.display()))?;
    writeln!(
        file,
        "ARTICLE_CODE,ARTICLE_DEMAND,LOCATION_ID,THM_ID,FLOOR,AISLE,COLUMN,SHELF,LEFT_OR_RIGHT,AVAILABLE_STOCK,NODE_ID,NODE_VISITED,THM_OPENED,IS_SELECTED,PICKED_AMOUNT,PICK_ORDER"
    )
    .map_err(|err| err.to_string())?;
    for row in rows {
        writeln!(
            file,
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
            row.article,
            row.demand,
            csv_escape(&row.location_id),
            csv_escape(&row.thm_id),
            csv_escape(&row.floor),
            row.aisle,
            row.column,
            row.shelf,
            csv_escape(&row.side),
            row.stock,
            csv_escape(&row.node_id),
            if row.node_visited { 1 } else { 0 },
            if row.thm_opened { 1 } else { 0 },
            if row.selected { 1 } else { 0 },
            row.picked_amount,
            row.pick_order.map(|v| v.to_string()).unwrap_or_default()
        )
        .map_err(|err| err.to_string())?;
    }
    Ok(())
}

#[derive(Debug)]
struct AltRow {
    article: i32,
    demand: i32,
    location_id: String,
    thm_id: String,
    floor: String,
    aisle: i32,
    column: i32,
    shelf: i32,
    side: String,
    stock: i32,
    node_id: String,
    node_visited: bool,
    thm_opened: bool,
    selected: bool,
    picked_amount: i32,
    pick_order: Option<usize>,
}

fn node_id_map(locs: &[Loc]) -> BTreeMap<(String, Node), String> {
    let mut keys = locs
        .iter()
        .map(|loc| (loc.floor.clone(), loc.node()))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();
    keys.sort_by(|a, b| {
        floor_index(&a.0)
            .cmp(&floor_index(&b.0))
            .then_with(|| a.1.aisle.cmp(&b.1.aisle))
            .then_with(|| a.1.column.cmp(&b.1.column))
    });
    keys.into_iter()
        .enumerate()
        .map(|(idx, key)| (key, format!("n{:05}", idx + 1)))
        .collect()
}

fn write_summary_json(solution: &Solution, args: &Args, path: &Path) -> AppResult<()> {
    ensure_parent(path)?;
    let mut lines = Vec::new();
    lines.push("{".to_string());
    lines.push(format!(
        "  \"algorithm\": {},",
        json_string(&solution.algorithm)
    ));
    lines.push(format!(
        "  \"orders\": {},",
        json_string(&args.orders.display().to_string())
    ));
    lines.push(format!(
        "  \"stock\": {},",
        json_string(&args.stock.display().to_string())
    ));
    lines.push(format!("  \"objective_value\": {:.6},", solution.objective));
    lines.push(format!("  \"distance\": {:.6},", solution.total_distance));
    lines.push(format!("  \"floors\": {},", solution.total_floors));
    lines.push(format!("  \"thms\": {},", solution.total_thms));
    lines.push(format!("  \"pick_rows\": {},", solution.total_picks));
    lines.push(format!(
        "  \"visited_nodes\": {},",
        solution
            .floor_results
            .iter()
            .map(|floor| floor.route.len())
            .sum::<usize>()
    ));
    lines.push(format!("  \"solve_time\": {:.6},", solution.solve_time));
    lines.push("  \"notes\": {".to_string());
    for (idx, (key, value)) in solution.notes.iter().enumerate() {
        let suffix = if idx + 1 == solution.notes.len() {
            ""
        } else {
            ","
        };
        lines.push(format!(
            "    {}: {}{}",
            json_string(key),
            json_string(value),
            suffix
        ));
    }
    lines.push("  }".to_string());
    lines.push("}".to_string());
    fs::write(path, lines.join("\n"))
        .map_err(|err| format!("failed to write {}: {err}", path.display()))
}

fn print_report(solution: &Solution) {
    println!();
    println!("========================================================================");
    println!("  {} — RESULTS", solution.algorithm.to_ascii_uppercase());
    println!("========================================================================");
    println!();
    println!("  Objective value:            {:.2}", solution.objective);
    println!(
        "  Total distance:             {:.2} m",
        solution.total_distance
    );
    println!("  Active floors:              {}", solution.total_floors);
    println!("  Opened THMs:                {}", solution.total_thms);
    println!("  Pick rows:                  {}", solution.total_picks);
    for (key, value) in &solution.notes {
        println!("  {:<26}{}", format!("{key}:"), value);
    }
    println!();
    println!("  Floor details:");
    for floor in &solution.floor_results {
        println!(
            "    {}: {} locations, {} THMs, {} nodes, distance={:.1}m",
            floor.floor,
            floor.picks.len(),
            floor.opened_thms.len(),
            floor.route.len(),
            floor.route_distance
        );
    }
    println!();
    println!("  Total solve time:           {:.2} s", solution.solve_time);
    println!("========================================================================");
}

fn ensure_parent(path: &Path) -> AppResult<()> {
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)
                .map_err(|err| format!("failed to create {}: {err}", parent.display()))?;
        }
    }
    Ok(())
}

fn csv_escape(value: &str) -> String {
    if value.contains(',') || value.contains('"') || value.contains('\n') {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.to_string()
    }
}

fn json_string(value: &str) -> String {
    let escaped = value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t");
    format!("\"{escaped}\"")
}

fn parse_args() -> AppResult<Args> {
    let mut args = Args {
        orders: PathBuf::from("data/full/PickOrder.csv"),
        stock: PathBuf::from("data/full/StockData.csv"),
        distance_weight: 1.0,
        thm_weight: 15.0,
        floor_weight: 30.0,
        time_limit: 300.0,
        fallback_on_time_limit: true,
        fallback_alpha: 0.25,
        fallback_article_rcl_size: 6,
        fallback_location_rcl_size: 5,
        fallback_seed: 7,
        cleanup_operator: "2-opt".to_string(),
        cleanup_strategy: "best".to_string(),
        cleanup_passes: 3,
        floors: None,
        articles: None,
        output: PathBuf::from("outputs/benchmark_outputs/rust_current_best/current_best_pick.csv"),
        alt_output: PathBuf::from(
            "outputs/benchmark_outputs/rust_current_best/current_best_alt.csv",
        ),
        summary_output: PathBuf::from(
            "outputs/benchmark_outputs/rust_current_best/current_best_summary.json",
        ),
    };

    let raw: Vec<String> = env::args().skip(1).collect();
    let mut idx = 0usize;
    while idx < raw.len() {
        let flag = &raw[idx];
        if flag == "-h" || flag == "--help" {
            print_help();
            std::process::exit(0);
        }
        if flag == "--fallback-on-time-limit" {
            args.fallback_on_time_limit = true;
            idx += 1;
            continue;
        }
        if flag == "--no-fallback-on-time-limit" {
            args.fallback_on_time_limit = false;
            idx += 1;
            continue;
        }
        let value = raw
            .get(idx + 1)
            .ok_or_else(|| format!("missing value for {flag}"))?
            .clone();
        match flag.as_str() {
            "--orders" => args.orders = PathBuf::from(value),
            "--stock" => args.stock = PathBuf::from(value),
            "--distance-weight" => args.distance_weight = parse_f64_arg(flag, &value)?,
            "--thm-weight" => args.thm_weight = parse_f64_arg(flag, &value)?,
            "--floor-weight" => args.floor_weight = parse_f64_arg(flag, &value)?,
            "--time-limit" => args.time_limit = parse_f64_arg(flag, &value)?,
            "--fallback-alpha" => args.fallback_alpha = parse_f64_arg(flag, &value)?,
            "--fallback-article-rcl-size" => {
                args.fallback_article_rcl_size = parse_usize_arg(flag, &value)?
            }
            "--fallback-location-rcl-size" => {
                args.fallback_location_rcl_size = parse_usize_arg(flag, &value)?
            }
            "--fallback-seed" => args.fallback_seed = parse_u64_arg(flag, &value)?,
            "--cleanup-operator" => args.cleanup_operator = value,
            "--cleanup-strategy" => args.cleanup_strategy = value,
            "--cleanup-passes" => args.cleanup_passes = parse_usize_arg(flag, &value)?,
            "--floors" => args.floors = parse_floors(&value)?,
            "--articles" => args.articles = parse_articles(&value)?,
            "--output" => args.output = PathBuf::from(value),
            "--alternative-locations-output" => args.alt_output = PathBuf::from(value),
            "--summary-output" => args.summary_output = PathBuf::from(value),
            _ => return Err(format!("unknown argument {flag}")),
        }
        idx += 2;
    }
    Ok(args)
}

fn parse_f64_arg(flag: &str, value: &str) -> AppResult<f64> {
    value
        .parse::<f64>()
        .map_err(|err| format!("invalid {flag}: {err}"))
}

fn parse_usize_arg(flag: &str, value: &str) -> AppResult<usize> {
    value
        .parse::<usize>()
        .map_err(|err| format!("invalid {flag}: {err}"))
}

fn parse_u64_arg(flag: &str, value: &str) -> AppResult<u64> {
    value
        .parse::<u64>()
        .map_err(|err| format!("invalid {flag}: {err}"))
}

fn parse_floors(value: &str) -> AppResult<Option<BTreeSet<String>>> {
    let mut floors = BTreeSet::new();
    for token in value.split(',').map(str::trim).filter(|v| !v.is_empty()) {
        let Some(floor) = norm_floor(token) else {
            return Err(format!("invalid floor filter '{token}'"));
        };
        floors.insert(floor);
    }
    Ok(if floors.is_empty() {
        None
    } else {
        Some(floors)
    })
}

fn parse_articles(value: &str) -> AppResult<Option<BTreeSet<i32>>> {
    let mut articles = BTreeSet::new();
    for token in value.split(',').map(str::trim).filter(|v| !v.is_empty()) {
        let article = token
            .parse::<i32>()
            .map_err(|err| format!("invalid article filter '{token}': {err}"))?;
        articles.insert(article);
    }
    Ok(if articles.is_empty() {
        None
    } else {
        Some(articles)
    })
}

fn print_help() {
    println!("Rust current-best warehouse picking heuristic");
    println!();
    println!("Options:");
    println!("  --orders PATH");
    println!("  --stock PATH");
    println!("  --time-limit SECONDS              0 means unlimited");
    println!("  --fallback-on-time-limit | --no-fallback-on-time-limit");
    println!("  --cleanup-operator none|2-opt|swap|relocate");
    println!("  --cleanup-strategy best|first");
    println!("  --floors MZN1,MZN2");
    println!("  --articles 88,150,258");
    println!("  --output PATH");
    println!("  --alternative-locations-output PATH");
    println!("  --summary-output PATH");
}

// Hash f64 rank only through deterministic Ord wrappers above; this keeps clippy quiet
// when ArticleRank derives are intentionally manual.
#[allow(dead_code)]
fn _hash_f64<H: Hasher>(value: f64, state: &mut H) {
    value.to_bits().hash(state);
}

"""Interactive Windows launcher for warehouse solver scripts.

This script is intended to be started from ``run_windows.bat`` on Windows.
It asks the user for:

- which algorithm to run,
- whether to use the full data set or a custom/manual configuration,
- common objective weights,
- output directory and filenames,
- algorithm-specific parameters,
- and optional extra CLI arguments.

It then builds the correct Python command and executes the selected solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Iterable


@dataclass(frozen=True)
class ParamSpec:
    flag: str
    label: str
    default: str
    help_text: str = ""
    choices: tuple[str, ...] | None = None


@dataclass(frozen=True)
class AlgorithmSpec:
    key: str
    label: str
    script: str
    time_flag: str | None
    time_default: str | None
    extra_params: tuple[ParamSpec, ...]


ALGORITHMS: tuple[AlgorithmSpec, ...] = (
    AlgorithmSpec(
        key="current_best",
        label="Current best: LK seed + grouped insertion + GRASP fallback + cleanup",
        script="current_best_heuristic.py",
        time_flag="--time-limit",
        time_default="300",
        extra_params=(
            ParamSpec("--fallback-alpha", "Fallback alpha", "0.25"),
            ParamSpec("--fallback-article-rcl-size", "Fallback article RCL size", "6"),
            ParamSpec("--fallback-location-rcl-size", "Fallback location RCL size", "5"),
            ParamSpec("--fallback-seed", "Fallback random seed", "7"),
            ParamSpec(
                flag="--cleanup-operator",
                label="Route cleanup operator",
                default="2-opt",
                choices=("none", "2-opt", "swap", "relocate"),
            ),
            ParamSpec(
                flag="--cleanup-strategy",
                label="Route cleanup strategy",
                default="best",
                choices=("best", "first"),
            ),
            ParamSpec("--cleanup-passes", "Cleanup passes", "3"),
        ),
    ),
    AlgorithmSpec(
        key="regret",
        label="Route-aware regret greedy",
        script="regret_based_heuristic.py",
        time_flag=None,
        time_default=None,
        extra_params=(
            ParamSpec(
                flag="--construction-route-estimator",
                label="Construction route estimator",
                default="insertion",
                help_text="Use insertion or best_of_4 during construction.",
                choices=("insertion", "best_of_4"),
            ),
        ),
    ),
    AlgorithmSpec(
        key="grasp",
        label="GRASP multi-start",
        script="grasp_heuristic.py",
        time_flag="--time-limit",
        time_default="10",
        extra_params=(
            ParamSpec("--iterations", "Iterations", "25"),
            ParamSpec("--alpha", "RCL alpha", "0.25"),
            ParamSpec("--article-rcl-size", "Article RCL size", "6"),
            ParamSpec("--location-rcl-size", "Location RCL size", "5"),
            ParamSpec("--seed", "Random seed", "7"),
            ParamSpec(
                flag="--construction-route-estimator",
                label="Construction route estimator",
                default="insertion",
                choices=("insertion", "best_of_4"),
            ),
        ),
    ),
    AlgorithmSpec(
        key="vns",
        label="Variable Neighborhood Search",
        script="vns_heuristic.py",
        time_flag="--time-limit",
        time_default="20",
        extra_params=(
            ParamSpec("--seed-mode", "Seed mode", "fast_thm", choices=("fast_thm", "regret", "best")),
            ParamSpec("--max-neighborhood", "Max neighborhood", "4"),
            ParamSpec("--source-sample-size", "Source sample size", "48"),
            ParamSpec("--target-sample-size", "Target sample size", "6"),
            ParamSpec("--thm-sample-size", "THM sample size", "12"),
            ParamSpec("--floor-sample-size", "Floor sample size", "4"),
            ParamSpec("--max-locations-per-neighborhood", "Max locations per neighborhood", "10"),
            ParamSpec("--local-step-limit", "Local step limit", "24"),
            ParamSpec("--candidate-pool-size", "Candidate pool size", "6"),
            ParamSpec("--seed", "Random seed", "7"),
        ),
    ),
    AlgorithmSpec(
        key="lns",
        label="Large Neighborhood Search",
        script="lns_heuristic.py",
        time_flag="--time-limit",
        time_default="20",
        extra_params=(
            ParamSpec("--seed-mode", "Seed mode", "fast_thm", choices=("fast_thm", "regret", "best")),
            ParamSpec("--iterations", "Iterations", "200"),
            ParamSpec("--min-destroy-size", "Min destroy size", "2"),
            ParamSpec("--max-destroy-size", "Max destroy size", "6"),
            ParamSpec("--max-destroy-locations", "Max destroy locations", "24"),
            ParamSpec("--repair-target-limit", "Repair target limit", "6"),
            ParamSpec("--seed-local-step-limit", "Seed local step limit", "16"),
            ParamSpec("--repair-intensify-steps", "Repair intensify steps", "6"),
            ParamSpec("--source-sample-size", "Source sample size", "48"),
            ParamSpec("--target-sample-size", "Target sample size", "6"),
            ParamSpec("--thm-sample-size", "THM sample size", "12"),
            ParamSpec("--floor-sample-size", "Floor sample size", "4"),
            ParamSpec("--max-locations-per-neighborhood", "Max locations per neighborhood", "10"),
            ParamSpec("--restart-after", "Restart after", "16"),
            ParamSpec("--candidate-pool-size", "Candidate pool size", "6"),
            ParamSpec("--seed", "Random seed", "7"),
        ),
    ),
    AlgorithmSpec(
        key="alns",
        label="Adaptive Large Neighborhood Search",
        script="alns_heuristic.py",
        time_flag="--time-limit",
        time_default="20",
        extra_params=(
            ParamSpec("--seed-mode", "Seed mode", "fast_thm", choices=("fast_thm", "regret", "best")),
            ParamSpec("--iterations", "Iterations", "250"),
            ParamSpec("--min-destroy-size", "Min destroy size", "2"),
            ParamSpec("--max-destroy-size", "Max destroy size", "7"),
            ParamSpec("--max-destroy-locations", "Max destroy locations", "28"),
            ParamSpec("--seed-local-step-limit", "Seed local step limit", "16"),
            ParamSpec("--source-sample-size", "Source sample size", "48"),
            ParamSpec("--target-sample-size", "Target sample size", "6"),
            ParamSpec("--thm-sample-size", "THM sample size", "12"),
            ParamSpec("--floor-sample-size", "Floor sample size", "4"),
            ParamSpec("--max-locations-per-neighborhood", "Max locations per neighborhood", "10"),
            ParamSpec("--segment-length", "Segment length", "20"),
            ParamSpec("--reaction-factor", "Reaction factor", "0.35"),
            ParamSpec("--soft-accept-relaxation", "Soft-accept relaxation", "0.003"),
            ParamSpec("--soft-accept-probability", "Soft-accept probability", "0.10"),
            ParamSpec("--restart-after", "Restart after", "24"),
            ParamSpec("--candidate-pool-size", "Candidate pool size", "6"),
            ParamSpec("--seed", "Random seed", "7"),
        ),
    ),
    AlgorithmSpec(
        key="fast_thm",
        label="Fast THM-first + S-shape",
        script="fast_thm_first_s_shape_heuristic.py",
        time_flag="--time-limit",
        time_default="10",
        extra_params=(
            ParamSpec("--iterations", "Iterations", "12"),
            ParamSpec("--candidate-pool-size", "Candidate pool size", "6"),
            ParamSpec("--seed", "Random seed", "7"),
        ),
    ),
    AlgorithmSpec(
        key="thm_rr",
        label="THM-min + RR-style aisle DP",
        script="thm_min_rr_heuristic.py",
        time_flag="--thm-search-time-limit",
        time_default="10",
        extra_params=(),
    ),
    AlgorithmSpec(
        key="thm_sshape",
        label="THM-min + S-shape routing",
        script="thm_min_s_shape_heuristic.py",
        time_flag="--thm-search-time-limit",
        time_default="10",
        extra_params=(),
    ),
)


def ask_text(prompt: str, default: str | None = None, *, allow_blank: bool = True) -> str:
    while True:
        suffix = f" [{default}]" if default is not None and default != "" else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw:
            return raw
        if default is not None:
            return default
        if allow_blank:
            return ""
        print("Please enter a value.")


def ask_choice(prompt: str, options: Iterable[str], default: str | None = None) -> str:
    normalized = {option.lower(): option for option in options}
    printable = "/".join(options)
    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"{prompt} ({printable}){suffix}: ").strip()
        if not raw and default is not None:
            return default
        chosen = normalized.get(raw.lower())
        if chosen is not None:
            return chosen
        print(f"Please choose one of: {printable}")


def ask_menu(prompt: str, options: tuple[AlgorithmSpec, ...]) -> AlgorithmSpec:
    print(prompt)
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option.label} ({option.key})")
    while True:
        raw = input("Select number [1]: ").strip()
        if not raw:
            return options[0]
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        print("Please enter a valid number.")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    default_text = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{default_text}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def prompt_algorithm_params(spec: AlgorithmSpec) -> list[str]:
    args: list[str] = []
    print()
    print("Algorithm-specific parameters")
    if not spec.extra_params and spec.time_flag is None:
        print("  No extra parameters for this solver.")
        return args

    if spec.time_flag is not None:
        time_label = "Time limit (seconds)" if spec.time_flag == "--time-limit" else "THM search time limit (seconds)"
        time_value = ask_text(time_label, spec.time_default)
        if time_value != "":
            args.extend([spec.time_flag, time_value])

    for param in spec.extra_params:
        if param.choices is not None:
            value = ask_choice(param.label, param.choices, default=param.default)
        else:
            value = ask_text(param.label, param.default)
        if value != "":
            args.extend([param.flag, value])
    return args


def main() -> int:
    workspace = Path(__file__).resolve().parents[1]
    print("Windows Solver Launcher")
    print("=======================")
    print()

    algorithm = ask_menu("Choose algorithm", ALGORITHMS)

    print()
    print("Data mode")
    print("  1. Full data (data/full/PickOrder.csv + data/full/StockData.csv, no filters)")
    print("  2. Manual/custom")
    mode = ask_text("Select data mode", "1")
    while mode not in {"1", "2"}:
        print("Please enter 1 or 2.")
        mode = ask_text("Select data mode", "1")

    if mode == "1":
        orders = "data/full/PickOrder.csv"
        stock = "data/full/StockData.csv"
        floors = ""
        articles = ""
    else:
        print()
        print("Manual/custom input")
        orders = ask_text("Orders CSV path", "data/full/PickOrder.csv")
        stock = ask_text("Stock CSV path", "data/full/StockData.csv")
        floors = ask_text("Floor filter (comma-separated, blank for all)", "", allow_blank=True)
        articles = ask_text("Article filter (comma-separated, blank for all)", "", allow_blank=True)

    print()
    print("Objective weights")
    distance_weight = ask_text("Distance weight", "1")
    thm_weight = ask_text("THM weight", "15")
    floor_weight = ask_text("Floor weight", "30")

    print()
    output_dir_text = ask_text("Output directory", r"outputs\benchmark_outputs\windows_runs")
    run_name = ask_text("Run name", f"{algorithm.key}_run")
    pick_filename = ask_text("Pick output filename", f"{run_name}_pick.csv")
    alt_filename = ask_text(
        "Alternative output filename (blank to disable alternative CSV)",
        f"{run_name}_alt.csv",
        allow_blank=True,
    )

    extra_args: list[str] = []
    if ask_yes_no("Prompt for algorithm-specific parameters?", default=True):
        extra_args.extend(prompt_algorithm_params(algorithm))

    raw_extra = ask_text("Extra CLI arguments to append exactly as typed (optional)", "", allow_blank=True)
    if raw_extra:
        extra_args.extend(shlex.split(raw_extra, posix=False))

    output_dir = Path(output_dir_text)
    output_dir.mkdir(parents=True, exist_ok=True)
    pick_output = output_dir / pick_filename

    command = [
        sys.executable,
        str(workspace / "src" / algorithm.script),
        "--orders",
        orders,
        "--stock",
        stock,
        "--distance-weight",
        distance_weight,
        "--thm-weight",
        thm_weight,
        "--floor-weight",
        floor_weight,
        "--output",
        str(pick_output),
    ]

    if alt_filename:
        alt_output = output_dir / alt_filename
        command.extend(["--alternative-locations-output", str(alt_output)])
    else:
        alt_output = None

    if floors:
        command.extend(["--floors", floors])
    if articles:
        command.extend(["--articles", articles])
    command.extend(extra_args)

    print()
    print("Command preview")
    print("---------------")
    print(subprocess.list2cmdline(command))
    print()

    if not ask_yes_no("Run this command now?", default=True):
        print("Cancelled.")
        return 0

    print()
    print("Running...")
    print()
    completed = subprocess.run(command, cwd=workspace)
    print()
    if completed.returncode == 0:
        print("Run completed successfully.")
        print(f"Pick CSV: {pick_output}")
        if alt_output is not None:
            print(f"Alternative CSV: {alt_output}")
    else:
        print(f"Run failed with exit code {completed.returncode}.")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

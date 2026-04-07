from __future__ import annotations

import json
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "grasp_colab.ipynb"


def markdown_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def writefile_cell(filename: str, source: str) -> dict:
    body = f"%%writefile {filename}\n{source}"
    if not body.endswith("\n"):
        body += "\n"
    return code_cell(body)


def main() -> None:
    heuristic_common = (ROOT / "heuristic_common.py").read_text(encoding="utf-8")
    grasp_solver = (ROOT / "grasp_heuristic.py").read_text(encoding="utf-8")

    intro = textwrap.dedent(
        """
        # GRASP Heuristic for Google Colab

        This notebook is a self-contained Colab wrapper for the repository's `GRASP multi-start` warehouse picking solver.

        ## What it does

        - recreates the current Python solver files directly inside the Colab runtime,
        - uses `PickOrder.csv` and `StockData.csv` from the current runtime when they already exist,
        - asks for upload only when an input file is missing,
        - runs the GRASP heuristic with configurable filters, objective weights, and search controls,
        - previews the output tables,
        - and lets you download the result CSV files.

        ## Input files

        `PickOrder.csv` must contain at least:

        - `ARTICLE_CODE`
        - `AMOUNT`

        `StockData.csv` must contain at least:

        - `THM_ID`
        - `ARTICLE_CODE`
        - `FLOOR`
        - `AISLE`
        - `COLUMN`
        - `SHELF`
        - `LEFT_OR_RIGHT` or `RIGHT_OR_LEFT`
        - `STOCK`

        ## Typical Colab flow

        1. Run the two `%%writefile` cells once.
        2. Adjust the configuration cell if needed.
        3. Run the input resolution cell. It will use existing paths or ask for upload if a file is missing.
        4. Run the solve cell.
        5. Preview and download the generated outputs.
        """
    ).strip() + "\n"

    ensure_inputs = textwrap.dedent(
        """
        from pathlib import Path
        from google.colab import files

        def resolve_or_upload(path_str: str) -> str:
            path = Path(path_str)
            if path.exists():
                print(f"Using existing file: {path.resolve()}")
                return str(path)

            print(f"Missing file: {path_str}")
            print("Please upload it from your computer.")
            uploaded = files.upload()

            if uploaded:
                print("Uploaded files:")
                for name in uploaded:
                    print(f"  - {name}")

            if path.exists():
                return str(path)

            basename_path = Path(path.name)
            if basename_path.exists():
                print(f"Using uploaded file instead: {basename_path.resolve()}")
                return str(basename_path)

            raise FileNotFoundError(
                f"'{path_str}' was not found before or after upload. "
                "Update ORDER_PATH/STOCK_PATH if the uploaded file has a different name."
            )

        print("Current working directory:", Path.cwd())
        print("Current files:")
        for path in sorted(Path(".").iterdir()):
            if path.is_file():
                print(f"  - {path.name}")

        ORDER_PATH = resolve_or_upload(ORDER_PATH)
        STOCK_PATH = resolve_or_upload(STOCK_PATH)

        print("\\nResolved input paths:")
        print("  ORDER_PATH =", ORDER_PATH)
        print("  STOCK_PATH =", STOCK_PATH)
        """
    ).strip() + "\n"

    config = textwrap.dedent(
        """
        ORDER_PATH = "PickOrder.csv"
        STOCK_PATH = "StockData.csv"

        # Optional filters:
        # FLOOR_FILTER examples: None, "MZN1", "MZN1,MZN2"
        # ARTICLE_FILTER examples: None, "258,376,471"
        FLOOR_FILTER = None
        ARTICLE_FILTER = None

        DISTANCE_WEIGHT = 1.0
        THM_WEIGHT = 15.0
        FLOOR_WEIGHT = 30.0

        ITERATIONS = 25
        TIME_LIMIT = 10.0
        ALPHA = 0.25
        ARTICLE_RCL_SIZE = 6
        LOCATION_RCL_SIZE = 5
        SEED = 7

        # "insertion" is the default fast route estimator used during construction.
        # "best_of_4" is available if you want a more exploratory construction scorer.
        CONSTRUCTION_ROUTE_ESTIMATOR = "insertion"

        PICK_OUTPUT = "PickDataOutput_GRASP.csv"
        ALT_OUTPUT = "AlternativeLocationsOutput_GRASP.csv"
        """
    ).strip() + "\n"

    input_preview = textwrap.dedent(
        """
        import csv
        from itertools import islice

        def preview_csv(path: str, rows: int = 5) -> None:
            print(f"\\nPreview: {path}")
            with open(path, newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                print("Columns:", reader.fieldnames)
                for row in islice(reader, rows):
                    print(row)

        preview_csv(ORDER_PATH)
        preview_csv(STOCK_PATH)
        """
    ).strip() + "\n"

    solve = textwrap.dedent(
        """
        from pathlib import Path

        from grasp_heuristic import solve
        from heuristic_common import (
            parse_article_list,
            parse_floor_list,
            print_report,
            write_alternative_locations_csv,
            write_pick_csv,
        )

        floors = parse_floor_list(FLOOR_FILTER)
        articles = parse_article_list(ARTICLE_FILTER)

        solution = solve(
            ORDER_PATH,
            STOCK_PATH,
            floors=floors,
            articles=articles,
            distance_weight=DISTANCE_WEIGHT,
            thm_weight=THM_WEIGHT,
            floor_weight=FLOOR_WEIGHT,
            iterations=ITERATIONS,
            time_limit=TIME_LIMIT,
            alpha=ALPHA,
            article_rcl_size=ARTICLE_RCL_SIZE,
            location_rcl_size=LOCATION_RCL_SIZE,
            seed=SEED,
            construction_route_estimator=CONSTRUCTION_ROUTE_ESTIMATOR,
        )

        print_report(solution)

        pick_output_path = write_pick_csv(solution, PICK_OUTPUT)
        print(f"\\nPick output written to: {Path(pick_output_path).resolve()}")

        alt_output_path = None
        if ALT_OUTPUT:
            alt_output_path = write_alternative_locations_csv(solution, ALT_OUTPUT)
            print(f"Alternative locations written to: {Path(alt_output_path).resolve()}")
        """
    ).strip() + "\n"

    preview_outputs = textwrap.dedent(
        """
        import pandas as pd

        display(pd.read_csv(pick_output_path).head(20))

        if alt_output_path is not None:
            display(pd.read_csv(alt_output_path).head(20))
        """
    ).strip() + "\n"

    download_outputs = textwrap.dedent(
        """
        from google.colab import files

        files.download(str(pick_output_path))

        if alt_output_path is not None:
            files.download(str(alt_output_path))
        """
    ).strip() + "\n"

    notes = textwrap.dedent(
        """
        ## Notes

        - Iteration 1 is deterministic in this solver and acts as an elite seed before randomized GRASP iterations begin.
        - To rerun with different search settings, edit the configuration cell and rerun the input resolution, solve, preview, and download cells.
        - If the configured file path already exists in Colab, no upload prompt appears.
        - If your stock file uses `RIGHT_OR_LEFT` instead of `LEFT_OR_RIGHT`, the solver already supports that.
        - The notebook uses the exact solver code from this repository snapshot, so Colab results should match local runs for the same inputs.
        """
    ).strip() + "\n"

    notebook = {
        "cells": [
            markdown_cell(intro),
            writefile_cell("heuristic_common.py", heuristic_common),
            writefile_cell("grasp_heuristic.py", grasp_solver),
            code_cell(config),
            code_cell(ensure_inputs),
            code_cell(input_preview),
            code_cell(solve),
            code_cell(preview_outputs),
            code_cell(download_outputs),
            markdown_cell(notes),
        ],
        "metadata": {
            "colab": {
                "name": OUTPUT.name,
                "provenance": [],
                "include_colab_link": True,
            },
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    OUTPUT.write_text(json.dumps(notebook, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Backward-compatible entry point for the 10-item Gurobi vs C++ benchmark."""

from benchmark_gurobi_cpp import main


if __name__ == "__main__":
    raise SystemExit(main("10item"))

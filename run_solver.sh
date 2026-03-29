#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

export GRB_LICENSE_FILE="$SCRIPT_DIR/gurobi.lic"

exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/gurobi_pick_model.py" "$@"

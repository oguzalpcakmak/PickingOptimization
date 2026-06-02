#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOLVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EMSDK_DIR="${EMSDK_DIR:-$HOME/.local/share/emsdk}"

if [[ ! -f "$EMSDK_DIR/emsdk_env.sh" ]]; then
  echo "Emscripten SDK not found at $EMSDK_DIR" >&2
  echo "Set EMSDK_DIR or install emsdk before building." >&2
  exit 1
fi

export EMSDK_QUIET=1
source "$EMSDK_DIR/emsdk_env.sh"

emcmake cmake \
  -S "$SOLVER_DIR" \
  -B "$SOLVER_DIR/build-wasm" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF

cmake --build "$SOLVER_DIR/build-wasm" --target picking_solver_wasm lkh_wasm --parallel

printf '\nWASM artifacts:\n'
ls -lh \
  "$SOLVER_DIR/build-wasm/picking_solver.mjs" \
  "$SOLVER_DIR/build-wasm/picking_solver.wasm" \
  "$SOLVER_DIR/build-wasm/lkh.mjs" \
  "$SOLVER_DIR/build-wasm/lkh.wasm"

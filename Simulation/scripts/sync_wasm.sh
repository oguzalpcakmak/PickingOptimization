#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMULATION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SIMULATION_DIR/.." && pwd)"
WASM_BUILD_DIR="$REPO_ROOT/cpp_solver/build-wasm"
PUBLIC_WASM_DIR="$SIMULATION_DIR/public/wasm"
CLIENT_LKH_ENABLED="${VITE_ENABLE_CLIENT_LKH:-true}"

"$REPO_ROOT/cpp_solver/scripts/build_wasm.sh"

mkdir -p "$PUBLIC_WASM_DIR"
cp "$WASM_BUILD_DIR/picking_solver.mjs" "$PUBLIC_WASM_DIR/picking_solver.mjs"
cp "$WASM_BUILD_DIR/picking_solver.wasm" "$PUBLIC_WASM_DIR/picking_solver.wasm"
if [[ "$CLIENT_LKH_ENABLED" != "false" ]]; then
  cp "$WASM_BUILD_DIR/lkh.mjs" "$PUBLIC_WASM_DIR/lkh.mjs"
  cp "$WASM_BUILD_DIR/lkh.wasm" "$PUBLIC_WASM_DIR/lkh.wasm"
else
  rm -f "$PUBLIC_WASM_DIR/lkh.mjs" "$PUBLIC_WASM_DIR/lkh.wasm"
fi

printf '\nSimulation WASM assets synced:\n'
ls -lh "$PUBLIC_WASM_DIR/picking_solver.mjs" "$PUBLIC_WASM_DIR/picking_solver.wasm"
if [[ "$CLIENT_LKH_ENABLED" != "false" ]]; then
  ls -lh "$PUBLIC_WASM_DIR/lkh.mjs" "$PUBLIC_WASM_DIR/lkh.wasm"
else
  printf 'Client-side LKH assets omitted (VITE_ENABLE_CLIENT_LKH=false).\n'
fi

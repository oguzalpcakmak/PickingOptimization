import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const simulationDir = resolve(scriptDir, '..');
const publicWasmDir = resolve(simulationDir, 'public', 'wasm');
const clientLkhEnabled = process.env.VITE_ENABLE_CLIENT_LKH !== 'false';
const requiredFiles = [
  'picking_solver.mjs',
  'picking_solver.wasm',
  ...(clientLkhEnabled ? ['lkh.mjs', 'lkh.wasm'] : [])
];
const missingFiles = requiredFiles.filter((file) => !existsSync(resolve(publicWasmDir, file)));

if (process.argv.includes('--if-missing') && missingFiles.length === 0) {
  console.log('Simulation WASM assets already exist.');
  process.exit(0);
}

if (missingFiles.length > 0) {
  console.log(`Missing Simulation WASM assets: ${missingFiles.join(', ')}`);
}

const result = spawnSync('bash', ['./scripts/sync_wasm.sh'], {
  cwd: simulationDir,
  env: process.env,
  stdio: 'inherit'
});

if (result.error) {
  console.error(`Unable to start the WASM sync script: ${result.error.message}`);
  console.error('Install Bash and the Emscripten SDK, then run "npm run wasm:sync" again.');
  process.exit(1);
}

process.exit(result.status ?? 1);

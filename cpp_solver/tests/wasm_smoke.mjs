import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const solverDir = path.resolve(testDir, '..');
const repoRoot = path.resolve(solverDir, '..');
const wasmBuildDir = path.resolve(solverDir, 'build-wasm');
const wasmModulePath = path.resolve(wasmBuildDir, 'picking_solver.mjs');
const lkhWasmModulePath = path.resolve(wasmBuildDir, 'lkh.mjs');
const lkhNativePath = path.resolve(repoRoot, 'external/LKH-3.0.14/LKH');
const nativeBinary = path.resolve(solverDir, 'build', 'picking_current_best_cpp');
const ordersLabel = 'data/full/PickOrder.csv';
const stockLabel = 'data/full/StockData.csv';
const fullDataset = process.argv.includes('--full');
const lkhMode = process.argv.includes('--lkh');
const articlesCsv = fullDataset ? '' : '567,577,606,609,699';
const timeLimit = fullDataset ? 120 : 20;
const ordersCsv = fs.readFileSync(path.resolve(repoRoot, ordersLabel), 'utf8');
const stockCsv = fs.readFileSync(path.resolve(repoRoot, stockLabel), 'utf8');

function sha256(value) {
  return createHash('sha256').update(value).digest('hex');
}

function normalizedSummary(summaryJson) {
  const summary = JSON.parse(summaryJson);
  delete summary.solve_time;
  for (const key of [
    'ascending_grouped_phase_sec',
    'prep_single_location_sec',
    'route_cleanup_time',
    'seed_route_sec',
    'lkh_path',
    'lkh_runner'
  ]) {
    delete summary.notes[key];
  }
  return summary;
}

function runNativeReference(outputDir) {
  const pickPath = path.join(outputDir, 'pick.csv');
  const altPath = path.join(outputDir, 'alt.csv');
  const summaryPath = path.join(outputDir, 'summary.json');
  const args = [
    '--orders',
    ordersLabel,
    '--stock',
    stockLabel,
    '--time-limit',
    String(timeLimit),
    '--seed-route-optimizer',
    lkhMode ? 'lkh' : 'cpp',
    '--article-selection',
    'grouped',
    '--candidate-group-width',
    '2',
    '--fallback-method',
    'grasp',
    '--cleanup-operator',
    '2-opt',
    '--cleanup-strategy',
    'best',
    '--cleanup-passes',
    '3',
    '--output',
    pickPath,
    '--alternative-locations-output',
    altPath,
    '--summary-output',
    summaryPath
  ];
  if (lkhMode) args.push('--lkh-path', lkhNativePath);
  if (articlesCsv) args.push('--articles', articlesCsv);
  execFileSync(nativeBinary, args, { cwd: repoRoot, stdio: 'ignore' });
  return {
    pickCsv: fs.readFileSync(pickPath, 'utf8'),
    alternativeLocationsCsv: fs.readFileSync(altPath, 'utf8'),
    summaryJson: fs.readFileSync(summaryPath, 'utf8')
  };
}

const createPickingSolver = (await import(pathToFileURL(wasmModulePath).href)).default;
const wasm = await createPickingSolver({
  locateFile(file) {
    return path.resolve(wasmBuildDir, file);
  }
});

const wasmOptions = {
  ordersLabel,
  stockLabel,
  distanceWeight: 1,
  thmWeight: 15,
  floorWeight: 30,
  timeLimit,
  fallbackOnTimeLimit: true,
  fallbackAlpha: 0.25,
  fallbackArticleRclSize: 6,
  fallbackLocationRclSize: 5,
  fallbackSeed: 7,
  fallbackMethod: 'grasp',
  lkhPrecision: 1000,
  lkhRuns: 1,
  lkhSeed: 1,
  lkhMaxTrials: 0,
  candidateGroupWidth: 2,
  articleSelection: 'grouped',
  cleanupOperator: '2-opt',
  cleanupStrategy: 'best',
  cleanupPasses: 3,
  cleanupMaxTime: 120,
  cleanupFallbackPasses: 3,
  floorsCsv: '',
  articlesCsv
};

async function createLkhRunner() {
  const createLkh = (await import(pathToFileURL(lkhWasmModulePath).href)).default;
  const instances = await Promise.all(
    Array.from({ length: 6 }, () =>
      createLkh({
        noInitialRun: true,
        locateFile(file) {
          return path.resolve(wasmBuildDir, file);
        },
        print() {},
        printErr() {}
      })
    )
  );

  return (floor, tspText, parText) => {
    const lkh = instances.shift();
    assert.ok(lkh, `LKH instance pool exhausted for ${floor}`);
    lkh.FS.writeFile('/seed.tsp', tspText);
    lkh.FS.writeFile('/seed.par', parText);
    lkh.callMain(['/seed.par']);
    return lkh.FS.readFile('/seed.tour', { encoding: 'utf8' });
  };
}

const wasmResult = lkhMode
  ? wasm.solveCsvWithLkhRunner(ordersCsv, stockCsv, wasmOptions, await createLkhRunner())
  : wasm.solveCsvLkhFree(ordersCsv, stockCsv, wasmOptions);
const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'picking-wasm-smoke-'));

try {
  const nativeResult = runNativeReference(tempDir);
  assert.equal(wasmResult.pickCsv, nativeResult.pickCsv, 'pick CSV differs from native reference');
  assert.equal(
    wasmResult.alternativeLocationsCsv,
    nativeResult.alternativeLocationsCsv,
    'alternative locations CSV differs from native reference'
  );
  assert.deepEqual(
    normalizedSummary(wasmResult.summaryJson),
    normalizedSummary(nativeResult.summaryJson),
    'normalized summary differs from native reference'
  );

  const summary = JSON.parse(wasmResult.summaryJson);
  console.log(`${lkhMode ? 'LKH ' : ''}WASM ${fullDataset ? 'full regression' : 'smoke'} passed`);
  console.log(
    JSON.stringify(
      {
        objective: summary.objective_value,
        distance: summary.distance,
        floors: summary.floors,
        thms: summary.thms,
        pickRows: summary.pick_rows,
        seedRouteOptimizer: summary.notes.seed_route_optimizer,
        pickCsvSha256: sha256(wasmResult.pickCsv),
        alternativeCsvSha256: sha256(wasmResult.alternativeLocationsCsv)
      },
      null,
      2
    )
  );
} finally {
  fs.rmSync(tempDir, { recursive: true, force: true });
}

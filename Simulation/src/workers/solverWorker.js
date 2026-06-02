import * as XLSX from 'xlsx';
import {
  buildSolverInputs,
  findSheetName,
  isRowEmpty,
  normalizeRawRow,
  parseCsvRows,
  resolveSolverOptions
} from '../utils/solverInputProcessor.js';

let wasmPromise;
let lkhFactoryPromise;
const MAX_SEED_FLOORS = 6;
const CLIENT_LKH_ENABLED = import.meta.env.VITE_ENABLE_CLIENT_LKH !== 'false';

function postProgress(requestId, progress, detail) {
  self.postMessage({
    type: 'progress',
    requestId,
    progress,
    detail
  });
}

function sheetToRows(workbook, sheetName) {
  const sheet = workbook.Sheets[sheetName];
  if (!sheet) return [];

  return XLSX.utils
    .sheet_to_json(sheet, { defval: '', raw: false })
    .map(normalizeRawRow)
    .filter((row) => !isRowEmpty(row));
}

async function importWasmFactory(fileName) {
  const baseUrl = import.meta.env.BASE_URL || '/';
  const moduleUrl = new URL(`${baseUrl}wasm/${fileName}`, self.location.origin);
  const response = await fetch(moduleUrl, { method: 'HEAD' });
  const contentType = response.headers.get('content-type') || '';

  if (!response.ok || contentType.includes('text/html')) {
    throw new Error(
      `WASM modulu bulunamadi: ${fileName}. Simulation dizininde "npm run wasm:sync" komutunu calistirin.`
    );
  }

  return (await import(/* @vite-ignore */ moduleUrl.href)).default;
}

async function loadWasm() {
  if (!wasmPromise) {
    wasmPromise = (async () => {
      const baseUrl = import.meta.env.BASE_URL || '/';
      const createPickingSolver = await importWasmFactory('picking_solver.mjs');

      return createPickingSolver({
        locateFile(file) {
          return new URL(`${baseUrl}wasm/${file}`, self.location.origin).href;
        }
      });
    })();
  }

  return wasmPromise;
}

async function loadLkhFactory() {
  if (!lkhFactoryPromise) {
    lkhFactoryPromise = importWasmFactory('lkh.mjs');
  }

  return lkhFactoryPromise;
}

async function createLkhInstances() {
  const createLkh = await loadLkhFactory();
  const baseUrl = import.meta.env.BASE_URL || '/';

  return Promise.all(
    Array.from({ length: MAX_SEED_FLOORS }, () =>
      createLkh({
        noInitialRun: true,
        locateFile(file) {
          return new URL(`${baseUrl}wasm/${file}`, self.location.origin).href;
        },
        print() {},
        printErr() {}
      })
    )
  );
}

function createLkhRunner(instances, metrics) {
  return (floor, tspText, parText) => {
    const lkh = instances.shift();
    if (!lkh) throw new Error(`LKH instance pool tukendi: ${floor}`);

    const started = performance.now();
    lkh.FS.writeFile('/seed.tsp', tspText);
    lkh.FS.writeFile('/seed.par', parText);
    lkh.callMain(['/seed.par']);
    const tour = lkh.FS.readFile('/seed.tour', { encoding: 'utf8' });

    metrics.floorCount += 1;
    metrics.solveMs += performance.now() - started;
    return tour;
  };
}

async function solveWorkbook(requestId, payload) {
  const started = performance.now();
  postProgress(requestId, 10, 'loading-wasm');
  const wasm = await loadWasm();

  postProgress(requestId, 25, 'reading-workbook');
  const workbook = XLSX.read(payload.workbookBuffer, { type: 'array' });
  const pickSheetName = findSheetName(workbook, ['Grup Toplama Verisi']) || workbook.SheetNames[0];
  const stockSheetName = findSheetName(workbook, ['Stok Bilgisi']);

  if (!pickSheetName) {
    throw new Error('Workbook icinde pick sheet bulunamadi.');
  }
  if (!stockSheetName) {
    throw new Error(`"Stok Bilgisi" sheet'i bulunamadi. Mevcut sheetler: ${workbook.SheetNames.join(', ')}`);
  }

  postProgress(requestId, 40, 'preparing-inputs');
  const pickRows = sheetToRows(workbook, pickSheetName);
  const stockRows = sheetToRows(workbook, stockSheetName);
  const { orderCsv, stockCsv, stats: inputStats } = buildSolverInputs(pickRows, stockRows);
  const options = resolveSolverOptions(payload.options);
  const clientMode = payload.options?.clientMode === 'lkh' ? 'lkh' : 'cpp';
  const lkhMetrics = {
    floorCount: 0,
    instantiateMs: 0,
    solveMs: 0
  };
  let lkhInstances = [];

  if (clientMode === 'lkh') {
    if (!CLIENT_LKH_ENABLED) {
      throw new Error('Client-side LKH bu build icin feature flag ile kapali.');
    }
    postProgress(requestId, 48, 'loading-lkh');
    const instantiateStarted = performance.now();
    lkhInstances = await createLkhInstances();
    lkhMetrics.instantiateMs = performance.now() - instantiateStarted;
  }

  const wasmOptions = {
    ordersLabel: `${payload.fileName || 'uploaded.xlsx'}#orders.csv`,
    stockLabel: `${payload.fileName || 'uploaded.xlsx'}#stock.csv`,
    distanceWeight: 1,
    thmWeight: 15,
    floorWeight: 30,
    timeLimit: options.timeLimit,
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
    candidateGroupWidth: options.candidateGroupWidth,
    articleSelection: options.articleSelection,
    cleanupOperator: '2-opt',
    cleanupStrategy: 'best',
    cleanupPasses: 3,
    cleanupMaxTime: 120,
    cleanupFallbackPasses: 3,
    floorsCsv: '',
    articlesCsv: ''
  };

  postProgress(requestId, 55, 'solving');
  const artifacts =
    clientMode === 'lkh'
      ? wasm.solveCsvWithLkhRunner(orderCsv, stockCsv, wasmOptions, createLkhRunner(lkhInstances, lkhMetrics))
      : wasm.solveCsvLkhFree(orderCsv, stockCsv, wasmOptions);

  postProgress(requestId, 90, 'parsing-output');
  return {
    ok: true,
    options,
    inputStats,
    summary: JSON.parse(artifacts.summaryJson),
    pickRows: parseCsvRows(artifacts.pickCsv),
    alternativeRows: parseCsvRows(artifacts.alternativeLocationsCsv),
    runtime: {
      mode: 'wasm-worker',
      seedRouteOptimizer: clientMode,
      lkhAvailable: CLIENT_LKH_ENABLED,
      elapsedMs: performance.now() - started,
      lkhFloorCount: lkhMetrics.floorCount,
      lkhInstantiateMs: lkhMetrics.instantiateMs,
      lkhSolveMs: lkhMetrics.solveMs
    }
  };
}

self.addEventListener('message', async (event) => {
  const { type, requestId, payload } = event.data || {};
  if (type !== 'solve') return;

  try {
    const result = await solveWorkbook(requestId, payload);
    self.postMessage({ type: 'result', requestId, result });
  } catch (error) {
    console.error('[solver-worker]', {
      requestId,
      clientMode: payload?.options?.clientMode || 'cpp',
      message: error?.message,
      stack: error?.stack
    });
    self.postMessage({
      type: 'error',
      requestId,
      error: error?.message || 'WASM solver calistirilirken hata olustu.'
    });
  }
});

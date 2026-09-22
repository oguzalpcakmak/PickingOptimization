import express from 'express';
import multer from 'multer';
import * as XLSX from 'xlsx';
import Papa from 'papaparse';
import { spawn } from 'node:child_process';
import crypto from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  aggregateSolverSummaries,
  annotateRowsWithAccount,
  buildSolverInputGroups as buildSolverInputGroupsCommon,
  parseCsvRows as parseCsvRowsCommon,
  resolveSolverOptions as resolveSolverOptionsCommon
} from '../src/utils/solverInputProcessor.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const appRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(appRoot, '..');
const distDir = path.join(appRoot, 'dist');
const runRoot = path.join(appRoot, 'tmp', 'solver-runs');
const solveJobs = new Map();
const JOB_RETENTION_MS = 60 * 60 * 1000;
const solveAttempts = new Map();
const SOLVE_RATE_WINDOW_MS = Number(process.env.SOLVE_RATE_WINDOW_MS || 10 * 60 * 1000);
const SOLVE_RATE_MAX = Number(process.env.SOLVE_RATE_MAX || 5);
const MAX_CONCURRENT_SOLVERS = Number(process.env.MAX_CONCURRENT_SOLVERS || 1);
const TURNSTILE_SECRET_FILE = process.env.TURNSTILE_SECRET_FILE || '/etc/picking-optimization/turnstile-secret';
const TURNSTILE_SECRET_KEY = process.env.TURNSTILE_SECRET_KEY || (
  existsSync(TURNSTILE_SECRET_FILE) ? readFileSync(TURNSTILE_SECRET_FILE, 'utf8').trim() : ''
);
const TURNSTILE_REQUIRED = process.env.TURNSTILE_REQUIRED === '1';
let activeSolverRuns = 0;

const PORT = Number(process.env.PORT || 5174);
const MAX_UPLOAD_MB = Number(process.env.MAX_UPLOAD_MB || 80);
const DEFAULT_SOLVER_PATH = path.join(repoRoot, 'cpp_solver', 'build', 'picking_current_best_cpp');
const DEFAULT_LKH_PATH = path.join(repoRoot, 'external', 'LKH-3.0.14', 'LKH');

const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: MAX_UPLOAD_MB * 1024 * 1024
  }
});

const VALID_FLOORS = new Set(['MZN1', 'MZN2', 'MZN3', 'MZN4', 'MZN5', 'MZN6']);
const ARTICLE_SELECTIONS = new Set(['grouped', 'bucket-cheapest', 'global-cheapest']);

function clientIp(req) {
  return String(req.headers['cf-connecting-ip'] || req.ip || req.socket.remoteAddress || 'unknown');
}

function enforceSolveRateLimit(req, res, next) {
  const now = Date.now();
  const ip = clientIp(req);
  const attempts = (solveAttempts.get(ip) || []).filter((timestamp) => now - timestamp < SOLVE_RATE_WINDOW_MS);
  if (attempts.length >= SOLVE_RATE_MAX) {
    const retryAfter = Math.max(1, Math.ceil((SOLVE_RATE_WINDOW_MS - (now - attempts[0])) / 1000));
    res.set('Retry-After', String(retryAfter));
    res.status(429).json({ error: 'Cok fazla cozum istegi gonderildi. Lutfen daha sonra tekrar deneyin.' });
    return;
  }
  attempts.push(now);
  solveAttempts.set(ip, attempts);
  next();
}

async function verifyTurnstile(token, ip) {
  if (!TURNSTILE_REQUIRED) return;
  if (!TURNSTILE_SECRET_KEY) {
    const error = new Error('Turnstile sunucu anahtari yapilandirilmamis.');
    error.statusCode = 503;
    throw error;
  }
  if (!token) {
    const error = new Error('Guvenlik dogrulamasi eksik.');
    error.statusCode = 403;
    throw error;
  }

  const body = new URLSearchParams({ secret: TURNSTILE_SECRET_KEY, response: token });
  if (ip && ip !== 'unknown') body.set('remoteip', ip);
  const response = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body,
    signal: AbortSignal.timeout(10_000)
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || result.success !== true) {
    const error = new Error('Guvenlik dogrulamasi basarisiz. Sayfayi yenileyip tekrar deneyin.');
    error.statusCode = 403;
    throw error;
  }
}

function sanitizeColumnName(name) {
  return String(name ?? '').replace(/^\uFEFF/, '').trim();
}

function normalizeRawRow(row) {
  return Object.entries(row || {}).reduce((acc, [key, value]) => {
    acc[sanitizeColumnName(key)] = value;
    return acc;
  }, {});
}

function isRowEmpty(row) {
  return Object.values(row || {}).every((value) => String(value ?? '').trim() === '');
}

function getValue(row, names) {
  for (const name of names) {
    if (!Object.prototype.hasOwnProperty.call(row, name)) continue;
    const value = row[name];
    if (value === undefined || value === null) continue;
    if (String(value).trim() !== '') return value;
  }
  return '';
}

function toText(value) {
  return String(value ?? '').trim();
}

function toInt(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.trunc(value);
  }

  const text = toText(value).replace(',', '.');
  if (!text) return null;

  const parsed = Number.parseFloat(text);
  if (!Number.isFinite(parsed)) return null;
  return Math.trunc(parsed);
}

function normalizeFloor(value) {
  const floor = toText(value).toUpperCase();
  return VALID_FLOORS.has(floor) ? floor : null;
}

function normalizeSide(value) {
  const side = toText(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase();
  if (side.startsWith('L') || side === 'SOL') return 'L';
  if (side.startsWith('R') || side === 'SAG') return 'R';
  return null;
}

function csvEscape(value) {
  const text = String(value ?? '');
  if (!/[",\n\r]/.test(text)) return text;
  return `"${text.replaceAll('"', '""')}"`;
}

function rowsToCsv(headers, rows) {
  const lines = [headers.join(',')];
  for (const row of rows) {
    lines.push(headers.map((header) => csvEscape(row[header])).join(','));
  }
  return `${lines.join('\n')}\n`;
}

function safePathPart(value) {
  const safe = String(value || 'NO_ACCOUNT').replace(/[^a-z0-9._-]+/gi, '_');
  return safe || 'NO_ACCOUNT';
}

function parseCsvRows(text) {
  const parsed = Papa.parse(text, {
    header: true,
    skipEmptyLines: true,
    transformHeader: sanitizeColumnName
  });

  const parseErrors = parsed.errors.filter((error) => error.code !== 'UndetectableDelimiter');
  if (parseErrors.length > 0) {
    throw new Error(parseErrors[0].message);
  }

  return parsed.data.map(normalizeRawRow).filter((row) => !isRowEmpty(row));
}

function findSheetName(workbook, candidates) {
  const sheetLookup = new Map(
    workbook.SheetNames.map((name) => [sanitizeColumnName(name).toLowerCase(), name])
  );

  for (const candidate of candidates) {
    const match = sheetLookup.get(candidate.toLowerCase());
    if (match) return match;
  }

  return null;
}

function sheetToRows(workbook, sheetName) {
  const sheet = workbook.Sheets[sheetName];
  if (!sheet) return [];

  return XLSX.utils
    .sheet_to_json(sheet, { defval: '', raw: false })
    .map(normalizeRawRow)
    .filter((row) => !isRowEmpty(row));
}

function rowsFromUpload(file, sheetCandidates = []) {
  if (!file) {
    throw new Error('Dosya yuklenmedi.');
  }

  const lowerFileName = file.originalname?.toLowerCase() || '';
  if (lowerFileName.endsWith('.csv')) {
    return parseCsvRows(file.buffer.toString('utf8'));
  }

  const workbook = XLSX.read(file.buffer, { type: 'buffer' });
  const sheetName = sheetCandidates.length > 0
    ? findSheetName(workbook, sheetCandidates) || workbook.SheetNames[0]
    : workbook.SheetNames[0];

  if (!sheetName) {
    throw new Error('Workbook icinde okunabilir sheet bulunamadi.');
  }

  return sheetToRows(workbook, sheetName);
}

function pickLocationFromRow(row) {
  const article = toInt(getValue(row, ['ARTICLE_CODE']));
  const amount = toInt(getValue(row, ['TOPLANAN_ADET', 'AMOUNT', 'PICKED_AMOUNT']));
  const floor = normalizeFloor(getValue(row, ['AREA', 'FLOOR']));
  const thm = toText(getValue(row, ['TOPLANAN_THM', 'THM_ID', 'PICKED_THM']));
  const aisle = toInt(getValue(row, ['AISLE', 'ACT_AISLE']));
  const column = toInt(getValue(row, ['X', 'COLUMN', 'ACT_X']));
  const shelf = toInt(getValue(row, ['Y', 'SHELF', 'ACT_Y']));
  const side = normalizeSide(getValue(row, ['Z', 'LEFT_OR_RIGHT', 'RIGHT_OR_LEFT', 'ACT_Z']));

  return {
    article,
    amount: amount && amount > 0 ? amount : 0,
    floor,
    thm,
    aisle,
    column,
    shelf,
    side
  };
}

function stockLocationFromRow(row) {
  const article = toInt(getValue(row, ['ARTICLE_CODE']));
  const floor = normalizeFloor(getValue(row, ['ACT_AREA', 'FLOOR', 'AREA']));
  const thm = toText(getValue(row, ['THM_ID', 'PICKED_THM', 'TOPLANAN_THM']));
  const aisle = toInt(getValue(row, ['ACT_AISLE', 'AISLE']));
  const column = toInt(getValue(row, ['ACT_X', 'COLUMN', 'X']));
  const shelf = toInt(getValue(row, ['ACT_Y', 'SHELF', 'Y']));
  const side = normalizeSide(getValue(row, ['ACT_Z', 'LEFT_OR_RIGHT', 'RIGHT_OR_LEFT', 'Z']));
  const stock = toInt(getValue(row, ['Stok', 'STOCK', 'STOCK_AMOUNT']));

  return {
    article,
    floor,
    thm,
    aisle,
    column,
    shelf,
    side,
    stock: stock && stock > 0 ? stock : 0
  };
}

function locationKey(location) {
  return [
    location.thm,
    location.article,
    location.floor,
    location.aisle,
    location.column,
    location.shelf,
    location.side
  ].join('|');
}

function hasCompleteLocation(location) {
  return Boolean(
    location.article &&
      location.floor &&
      location.thm &&
      location.aisle &&
      location.column &&
      location.shelf &&
      location.side
  );
}

function buildSolverInputs(pickRowsRaw, stockRowsRaw) {
  const pickRows = pickRowsRaw.map(normalizeRawRow).filter((row) => !isRowEmpty(row));
  const stockRows = stockRowsRaw.map(normalizeRawRow).filter((row) => !isRowEmpty(row));

  const demands = new Map();
  const pickedLocations = [];
  let skippedPickRows = 0;

  for (const row of pickRows) {
    const pick = pickLocationFromRow(row);
    if (!pick.article || !pick.amount || !pick.floor) {
      skippedPickRows += 1;
      continue;
    }

    demands.set(pick.article, (demands.get(pick.article) || 0) + pick.amount);

    if (hasCompleteLocation(pick)) {
      pickedLocations.push(pick);
    }
  }

  if (demands.size === 0) {
    throw new Error('Solver icin gecerli MZN pick talebi bulunamadi.');
  }

  const stockByLocation = new Map();
  let skippedStockRows = 0;

  for (const row of stockRows) {
    const stock = stockLocationFromRow(row);
    if (!hasCompleteLocation(stock)) {
      skippedStockRows += 1;
      continue;
    }

    const key = locationKey(stock);
    const existing = stockByLocation.get(key);
    if (existing) {
      existing.stock += stock.stock;
    } else {
      stockByLocation.set(key, { ...stock });
    }
  }

  let addedBack = 0;
  for (const pick of pickedLocations) {
    const key = locationKey(pick);
    const existing = stockByLocation.get(key);
    if (existing) {
      existing.stock += pick.amount;
    } else {
      stockByLocation.set(key, { ...pick, stock: pick.amount });
    }
    addedBack += pick.amount;
  }

  const orders = [...demands.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([article, amount]) => ({ ARTICLE_CODE: article, AMOUNT: amount }));

  const demandedArticles = new Set(demands.keys());
  const stock = [...stockByLocation.values()]
    .filter((row) => demandedArticles.has(row.article) && row.stock > 0)
    .sort((a, b) => {
      if (a.article !== b.article) return a.article - b.article;
      if (a.floor !== b.floor) return a.floor.localeCompare(b.floor);
      if (a.aisle !== b.aisle) return a.aisle - b.aisle;
      if (a.column !== b.column) return a.column - b.column;
      if (a.shelf !== b.shelf) return a.shelf - b.shelf;
      if (a.side !== b.side) return a.side.localeCompare(b.side);
      return a.thm.localeCompare(b.thm);
    })
    .map((row) => ({
      THM_ID: row.thm,
      ARTICLE_CODE: row.article,
      FLOOR: row.floor,
      AISLE: row.aisle,
      COLUMN: row.column,
      SHELF: row.shelf,
      LEFT_OR_RIGHT: row.side,
      STOCK: row.stock
    }));

  const stockByArticle = new Map();
  for (const row of stock) {
    stockByArticle.set(row.ARTICLE_CODE, (stockByArticle.get(row.ARTICLE_CODE) || 0) + row.STOCK);
  }

  const insufficient = orders.filter((order) => (stockByArticle.get(order.ARTICLE_CODE) || 0) < order.AMOUNT);
  if (insufficient.length > 0) {
    const preview = insufficient
      .slice(0, 5)
      .map((row) => `${row.ARTICLE_CODE}: ${stockByArticle.get(row.ARTICLE_CODE) || 0}/${row.AMOUNT}`)
      .join(', ');
    throw new Error(`Stok yetersiz olan urunler var (${preview}).`);
  }

  const orderCsv = rowsToCsv(['ARTICLE_CODE', 'AMOUNT'], orders);
  const stockCsv = rowsToCsv(
    ['THM_ID', 'ARTICLE_CODE', 'FLOOR', 'AISLE', 'COLUMN', 'SHELF', 'LEFT_OR_RIGHT', 'STOCK'],
    stock
  );

  const totalDemand = orders.reduce((sum, row) => sum + row.AMOUNT, 0);

  return {
    orderCsv,
    stockCsv,
    stats: {
      pickRows: pickRows.length,
      stockRows: stockRows.length,
      orderArticles: orders.length,
      totalDemand,
      solverStockRows: stock.length,
      addedBack,
      skippedPickRows,
      skippedStockRows
    }
  };
}

function clampNumber(value, min, max, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

function resolveSolverOptions(body) {
  const profile = body.profile === 'fast' ? 'fast' : 'quality';
  const requestedSelection = toText(body.articleSelection);
  const articleSelection = ARTICLE_SELECTIONS.has(requestedSelection)
    ? requestedSelection
    : profile === 'fast'
      ? 'grouped'
      : 'bucket-cheapest';

  return {
    profile,
    articleSelection,
    candidateGroupWidth: Math.round(clampNumber(body.candidateGroupWidth, 1, 20, 2)),
    timeLimit: clampNumber(body.timeLimit, 1, 1200, 1200)
  };
}

function runProcess(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    const maxBuffer = 250_000;

    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    const timeout = setTimeout(() => {
      timedOut = true;
      child.kill('SIGTERM');
      setTimeout(() => child.kill('SIGKILL'), 5000).unref();
    }, options.timeoutMs);

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
      if (stdout.length > maxBuffer) stdout = stdout.slice(-maxBuffer);
    });

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
      if (stderr.length > maxBuffer) stderr = stderr.slice(-maxBuffer);
    });

    child.on('error', (error) => {
      clearTimeout(timeout);
      reject(error);
    });

    child.on('close', (code) => {
      clearTimeout(timeout);
      if (timedOut) {
        reject(new Error(`Solver sure asimina ugradi. Son log: ${stderr || stdout}`));
        return;
      }
      if (code !== 0) {
        reject(new Error(`Solver ${code} koduyla bitti. ${stderr || stdout}`));
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

async function runSolver(runDir, options) {
  const solverPath = process.env.CPP_SOLVER_PATH || DEFAULT_SOLVER_PATH;
  const lkhPath = process.env.LKH_PATH || DEFAULT_LKH_PATH;
  if (!existsSync(solverPath)) {
    throw new Error(`C++ solver binary bulunamadi: ${solverPath}`);
  }

  const ordersPath = path.join(runDir, 'orders.csv');
  const stockPath = path.join(runDir, 'stock.csv');
  const pickPath = path.join(runDir, 'pick_output.csv');
  const altPath = path.join(runDir, 'alternative_locations.csv');
  const summaryPath = path.join(runDir, 'summary.json');

  const args = [
    '--orders',
    ordersPath,
    '--stock',
    stockPath,
    '--time-limit',
    String(options.timeLimit),
    '--fallback-method',
    'grasp',
    '--article-selection',
    options.articleSelection,
    '--candidate-group-width',
    String(options.candidateGroupWidth),
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

  if (existsSync(lkhPath)) {
    args.push('--seed-route-optimizer', 'lkh', '--lkh-path', lkhPath);
  } else {
    args.push('--seed-route-optimizer', 'cpp');
  }

  const timeoutMs = Math.round(options.timeLimit * 1000 + 180_000);
  await runProcess(solverPath, args, {
    cwd: repoRoot,
    env: process.env,
    timeoutMs
  });

  return {
    pickPath,
    altPath,
    summaryPath,
    solverPath,
    lkhPath: existsSync(lkhPath) ? lkhPath : null
  };
}

async function readJson(pathname) {
  return JSON.parse(await fs.readFile(pathname, 'utf8'));
}

async function solveUploadedRequest(req, runId) {
  const runDir = path.join(runRoot, runId);
  const requestStarted = Date.now();

  try {
    const singleFile = req.files?.file?.[0];
    const alokeFile = req.files?.alokeFile?.[0];
    const groupFile = req.files?.groupFile?.[0];
    const stockFile = req.files?.stockFile?.[0];

    if (!singleFile && (!alokeFile || !stockFile)) {
      throw new Error('Excel dosyasi yuklenmedi.');
    }

    const options = resolveSolverOptionsCommon(req.body || {});
    let groups;
    let inputStats;

    if (alokeFile && stockFile) {
      const alokeRows = rowsFromUpload(alokeFile, ['Aloke']);
      const stockRows = rowsFromUpload(stockFile, ['Stok Bilgisi', 'stok', 'Stock']);
      const benchmarkRows = groupFile
        ? rowsFromUpload(groupFile, ['Grup Toplama Verisi', 'Grup_Toplama', 'Grup Toplama'])
        : [];
      const prepared = buildSolverInputGroupsCommon(alokeRows, stockRows);
      groups = prepared.groups;
      const benchmarkAccounts = new Set(
        benchmarkRows.map((row) => String(row.ACCOUNTNO ?? '').trim()).filter(Boolean)
      );
      inputStats = {
        ...prepared.stats,
        alokeRows: alokeRows.length,
        benchmarkRows: benchmarkRows.length,
        benchmarkAccountCount: benchmarkAccounts.size
      };
    } else {
      const workbook = XLSX.read(singleFile.buffer, { type: 'buffer' });
      const pickSheetName = findSheetName(workbook, ['Grup Toplama Verisi']) || workbook.SheetNames[0];
      const stockSheetName = findSheetName(workbook, ['Stok Bilgisi']);

      if (!pickSheetName) throw new Error('Workbook icinde pick sheet bulunamadi.');
      if (!stockSheetName) {
        throw new Error(
          `"Stok Bilgisi" sheet'i bulunamadi. Mevcut sheetler: ${workbook.SheetNames.join(', ')}`
        );
      }

      const pickRows = sheetToRows(workbook, pickSheetName);
      const stockRows = sheetToRows(workbook, stockSheetName);
      const prepared = buildSolverInputGroupsCommon(pickRows, stockRows);
      groups = prepared.groups;
      inputStats = prepared.stats;
    }

    const pickRows = [];
    const alternativeRows = [];
    const summaries = [];
    let solverPath = null;
    let lkhPath = null;
    await fs.mkdir(runDir, { recursive: true });

    for (const group of groups) {
      const accountDir = path.join(runDir, safePathPart(group.stats.accountNo));
      await fs.mkdir(accountDir, { recursive: true });
      await fs.writeFile(path.join(accountDir, 'orders.csv'), group.orderCsv, 'utf8');
      await fs.writeFile(path.join(accountDir, 'stock.csv'), group.stockCsv, 'utf8');

      const solverFiles = await runSolver(accountDir, options);
      solverPath = solverFiles.solverPath;
      lkhPath = solverFiles.lkhPath;
      const [pickCsv, altCsv, summary] = await Promise.all([
        fs.readFile(solverFiles.pickPath, 'utf8'),
        fs.readFile(solverFiles.altPath, 'utf8'),
        readJson(solverFiles.summaryPath)
      ]);
      pickRows.push(...annotateRowsWithAccount(parseCsvRowsCommon(pickCsv), group.accountNo));
      alternativeRows.push(
        ...parseCsvRowsCommon(altCsv).map((row) => ({ ...row, ACCOUNTNO: group.stats.accountNo }))
      );
      summaries.push(summary);
    }

    return {
      ok: true,
      options,
      inputStats,
      summary: aggregateSolverSummaries(summaries, inputStats),
      pickRows,
      alternativeRows,
      runtime: {
        mode: 'server-native',
        solverPath,
        lkhPath,
        elapsedMs: Date.now() - requestStarted
      }
    };
  } finally {
    if (process.env.KEEP_SOLVER_RUNS !== '1') {
      await fs.rm(runDir, { recursive: true, force: true }).catch(() => {});
    }
  }
}

const app = express();

app.get('/api/solver/status', (_req, res) => {
  const solverPath = process.env.CPP_SOLVER_PATH || DEFAULT_SOLVER_PATH;
  const lkhPath = process.env.LKH_PATH || DEFAULT_LKH_PATH;
  res.json({
    ok: true,
    solverPath,
    solverAvailable: existsSync(solverPath),
    lkhPath,
    lkhAvailable: existsSync(lkhPath),
    turnstileRequired: TURNSTILE_REQUIRED,
    turnstileConfigured: Boolean(TURNSTILE_SECRET_KEY),
    activeSolverRuns,
    maxConcurrentSolvers: MAX_CONCURRENT_SOLVERS
  });
});

app.get('/api/solve/:jobId', (req, res) => {
  const job = solveJobs.get(req.params.jobId);
  if (!job) {
    res.status(404).json({ error: 'Cozum isi bulunamadi veya suresi doldu.' });
    return;
  }

  if (job.status === 'running') {
    res.status(202).json({ ok: true, jobId: req.params.jobId, status: 'running' });
    return;
  }

  solveJobs.delete(req.params.jobId);
  if (job.status === 'failed') {
    res.status(500).json({ error: job.error });
    return;
  }
  res.json(job.result);
});

app.post(
  '/api/solve',
  enforceSolveRateLimit,
  upload.fields([
    { name: 'file', maxCount: 1 },
    { name: 'alokeFile', maxCount: 1 },
    { name: 'groupFile', maxCount: 1 },
    { name: 'stockFile', maxCount: 1 }
  ]),
  async (req, res) => {
  const runId = `${Date.now()}-${crypto.randomUUID()}`;

  try {
    await verifyTurnstile(req.body?.turnstileToken, clientIp(req));
    if (activeSolverRuns >= MAX_CONCURRENT_SOLVERS) {
      res.status(429).json({ error: 'Solver su anda mesgul. Mevcut cozum tamamlaninca tekrar deneyin.' });
      return;
    }

    if (req.body?.async === '1') {
      activeSolverRuns += 1;
      solveJobs.set(runId, { status: 'running', createdAt: Date.now() });
      res.status(202).json({ ok: true, jobId: runId, status: 'running' });
      console.log(`[solver:${runId}] started ip=${clientIp(req)}`);

      solveUploadedRequest(req, runId)
        .then((result) => {
          solveJobs.set(runId, { status: 'completed', result, createdAt: Date.now() });
          console.log(`[solver:${runId}] completed elapsedMs=${result.runtime?.elapsedMs || 0}`);
        })
        .catch((error) => {
          console.error(error);
          solveJobs.set(runId, {
            status: 'failed',
            error: error.message || 'Solver calistirilirken hata olustu.',
            createdAt: Date.now()
          });
        })
        .finally(() => {
          activeSolverRuns = Math.max(0, activeSolverRuns - 1);
        });
      return;
    }

    activeSolverRuns += 1;
    try {
      res.json(await solveUploadedRequest(req, runId));
    } finally {
      activeSolverRuns = Math.max(0, activeSolverRuns - 1);
    }
  } catch (error) {
    if (!error.statusCode || error.statusCode >= 500) console.error(error);
    res.status(error.statusCode || 500).json({ error: error.message || 'Solver calistirilirken hata olustu.' });
  }
  }
);

setInterval(() => {
  const cutoff = Date.now() - JOB_RETENTION_MS;
  for (const [jobId, job] of solveJobs) {
    if (job.status !== 'running' && job.createdAt < cutoff) solveJobs.delete(jobId);
  }
  for (const [ip, attempts] of solveAttempts) {
    const recent = attempts.filter((timestamp) => Date.now() - timestamp < SOLVE_RATE_WINDOW_MS);
    if (recent.length > 0) solveAttempts.set(ip, recent);
    else solveAttempts.delete(ip);
  }
}, 10 * 60 * 1000).unref();

if (existsSync(distDir)) {
  app.use(express.static(distDir));
  app.get(/.*/, (req, res, next) => {
    if (req.path.startsWith('/api')) {
      next();
      return;
    }
    res.sendFile(path.join(distDir, 'index.html'));
  });
}

app.listen(PORT, () => {
  console.log(`Simulation API listening on http://localhost:${PORT}`);
});

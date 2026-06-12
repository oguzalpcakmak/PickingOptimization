import Papa from 'papaparse';

const VALID_FLOORS = new Set(['MZN1', 'MZN2', 'MZN3', 'MZN4', 'MZN5', 'MZN6']);
const ARTICLE_SELECTIONS = new Set(['grouped', 'bucket-cheapest', 'global-cheapest']);
const TOTAL_AISLES = 27;
const TOTAL_COLUMNS = 20;

export function sanitizeColumnName(name) {
  return String(name ?? '').replace(/^\uFEFF/, '').trim();
}

export function normalizeRawRow(row) {
  return Object.entries(row || {}).reduce((acc, [key, value]) => {
    acc[sanitizeColumnName(key)] = value;
    return acc;
  }, {});
}

export function isRowEmpty(row) {
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

function normalizeAccountNo(value) {
  return toText(value);
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

export function parseCsvRows(text) {
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

export function findSheetName(workbook, candidates) {
  const sheetLookup = new Map(
    workbook.SheetNames.map((name) => [sanitizeColumnName(name).toLowerCase(), name])
  );

  for (const candidate of candidates) {
    const match = sheetLookup.get(candidate.toLowerCase());
    if (match) return match;
  }

  return null;
}

function pickLocationFromRow(row) {
  const article = toInt(getValue(row, ['ARTICLE_CODE']));
  const amount = toInt(getValue(row, ['TOPLANAN_ADET', 'SUM(A.QUANTITY)', 'ADET', 'AMOUNT', 'PICKED_AMOUNT']));
  const floor = normalizeFloor(getValue(row, ['AREA', 'FLOOR']));
  const thm = toText(getValue(row, ['TOPLANAN_THM', 'TOPLAMA_THM', 'THM_ID', 'PICKED_THM', 'STOK_THM']));
  const aisle = toInt(getValue(row, ['AISLE', 'ACT_AISLE']));
  const column = toInt(getValue(row, ['X', 'COLUMN', 'ACT_X']));
  const shelf = toInt(getValue(row, ['Y', 'SHELF', 'ACT_Y']));
  const side = normalizeSide(getValue(row, ['Z', 'LEFT_OR_RIGHT', 'RIGHT_OR_LEFT', 'ACT_Z']));
  const accountNo = normalizeAccountNo(getValue(row, ['FROM_ACCOUNTNO', 'ACCOUNTNO']));
  const isAllocation = toText(getValue(row, ['FROM_ACCOUNTNO'])) !== '';

  return {
    article,
    amount: amount && amount > 0 ? amount : 0,
    floor,
    thm,
    aisle,
    column,
    shelf,
    side,
    accountNo,
    isAllocation
  };
}

function stockLocationFromRow(row) {
  const article = toInt(getValue(row, ['ARTICLE_CODE']));
  const floor = normalizeFloor(getValue(row, ['ACT_AREA', 'FLOOR', 'AREA']));
  const thm = toText(getValue(row, ['THM_ID', 'PICKED_THM', 'TOPLANAN_THM', 'STOK_THM']));
  const aisle = toInt(getValue(row, ['ACT_AISLE', 'AISLE']));
  const column = toInt(getValue(row, ['ACT_X', 'COLUMN', 'X']));
  const shelf = toInt(getValue(row, ['ACT_Y', 'SHELF', 'Y']));
  const side = normalizeSide(getValue(row, ['ACT_Z', 'LEFT_OR_RIGHT', 'RIGHT_OR_LEFT', 'Z']));
  const stock = toInt(getValue(row, ['Stok', 'STOCK', 'STOCK_AMOUNT', 'QTY_STOCK']));
  const accountNo = normalizeAccountNo(getValue(row, ['ACCOUNTNO', 'FROM_ACCOUNTNO']));

  return {
    article,
    floor,
    thm,
    aisle,
    column,
    shelf,
    side,
    stock: stock && stock > 0 ? stock : 0,
    accountNo
  };
}

function locationKey(location) {
  return [
    location.accountNo,
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

function hasValidSolverLocation(location) {
  return Boolean(
    hasCompleteLocation(location) &&
      location.aisle >= 1 &&
      location.aisle <= TOTAL_AISLES &&
      location.column >= 1 &&
      location.column <= TOTAL_COLUMNS
  );
}

function makeDemandKey(accountNo, article) {
  return `${accountNo}\u0000${article}`;
}

function splitDemandKey(key) {
  const [accountNo, article] = key.split('\u0000');
  return { accountNo, article: Number.parseInt(article, 10) };
}

function makeAccountLabel(accountNo) {
  return accountNo || 'NO_ACCOUNT';
}

function hasAccountValue(row) {
  return toText(getValue(row, ['FROM_ACCOUNTNO', 'ACCOUNTNO'])) !== '';
}

export function buildSolverInputGroups(pickRowsRaw, stockRowsRaw) {
  const pickRows = pickRowsRaw.map(normalizeRawRow).filter((row) => !isRowEmpty(row));
  const stockRows = stockRowsRaw.map(normalizeRawRow).filter((row) => !isRowEmpty(row));
  const useAccountGrouping = pickRows.some(hasAccountValue);

  const demands = new Map();
  const pickedLocations = [];
  let skippedPickRows = 0;
  let skippedOutOfLayoutPickRows = 0;
  let allocationDemandRows = 0;

  for (const row of pickRows) {
    const pick = pickLocationFromRow(row);
    if (!useAccountGrouping) {
      pick.accountNo = '';
    }
    if (!pick.article || !pick.amount || !pick.floor) {
      skippedPickRows += 1;
      continue;
    }

    if (pick.aisle && pick.column && !hasValidSolverLocation(pick)) {
      skippedOutOfLayoutPickRows += 1;
      continue;
    }

    const demandKey = makeDemandKey(pick.accountNo, pick.article);
    demands.set(demandKey, (demands.get(demandKey) || 0) + pick.amount);
    if (pick.isAllocation) {
      allocationDemandRows += 1;
    }

    if (hasValidSolverLocation(pick)) {
      pickedLocations.push(pick);
    }
  }

  if (demands.size === 0) {
    throw new Error('Solver icin gecerli MZN pick talebi bulunamadi.');
  }

  const stockByLocation = new Map();
  let skippedStockRows = 0;
  let skippedOutOfLayoutStockRows = 0;

  for (const row of stockRows) {
    const stock = stockLocationFromRow(row);
    if (!useAccountGrouping) {
      stock.accountNo = '';
    }
    if (!hasCompleteLocation(stock)) {
      skippedStockRows += 1;
      continue;
    }
    if (!hasValidSolverLocation(stock)) {
      skippedOutOfLayoutStockRows += 1;
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

  const demandsByAccount = new Map();
  for (const [key, amount] of demands) {
    const { accountNo, article } = splitDemandKey(key);
    if (!demandsByAccount.has(accountNo)) {
      demandsByAccount.set(accountNo, new Map());
    }
    demandsByAccount.get(accountNo).set(article, (demandsByAccount.get(accountNo).get(article) || 0) + amount);
  }

  const groups = [];

  for (const [accountNo, accountDemands] of [...demandsByAccount.entries()].sort((a, b) => {
    return makeAccountLabel(a[0]).localeCompare(makeAccountLabel(b[0]));
  })) {
    const orders = [...accountDemands.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([article, amount]) => ({ ARTICLE_CODE: article, AMOUNT: amount }));

    const demandedArticles = new Set(accountDemands.keys());
    const stock = [...stockByLocation.values()]
      .filter((row) => {
        if (!demandedArticles.has(row.article) || row.stock <= 0) return false;
        return !useAccountGrouping || row.accountNo === accountNo;
      })
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
        STOCK: row.stock,
        ACCOUNTNO: row.accountNo
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
      throw new Error(`${makeAccountLabel(accountNo)} ACCOUNTNO icin stok yetersiz urunler var (${preview}).`);
    }

    const orderCsv = rowsToCsv(['ARTICLE_CODE', 'AMOUNT'], orders);
    const stockCsv = rowsToCsv(
      ['THM_ID', 'ARTICLE_CODE', 'FLOOR', 'AISLE', 'COLUMN', 'SHELF', 'LEFT_OR_RIGHT', 'STOCK'],
      stock
    );

    groups.push({
      accountNo,
      orderCsv,
      stockCsv,
      stats: {
        accountNo: makeAccountLabel(accountNo),
        orderArticles: orders.length,
        totalDemand: orders.reduce((sum, row) => sum + row.AMOUNT, 0),
        solverStockRows: stock.length
      }
    });
  }

  const aggregateStats = {
    pickRows: pickRows.length,
    stockRows: stockRows.length,
    accountCount: groups.length,
    accountGroups: groups.map((group) => group.stats),
    orderArticles: groups.reduce((sum, group) => sum + group.stats.orderArticles, 0),
    totalDemand: groups.reduce((sum, group) => sum + group.stats.totalDemand, 0),
    solverStockRows: groups.reduce((sum, group) => sum + group.stats.solverStockRows, 0),
    addedBack,
    skippedPickRows,
    skippedStockRows,
    skippedOutOfLayoutPickRows,
    skippedOutOfLayoutStockRows,
    allocationDemandRows,
    accountGrouping: useAccountGrouping
  };

  return {
    groups,
    stats: aggregateStats
  };
}

export function buildSolverInputs(pickRowsRaw, stockRowsRaw) {
  const { groups, stats } = buildSolverInputGroups(pickRowsRaw, stockRowsRaw);
  if (groups.length !== 1) {
    throw new Error(`Tek solver input beklenirken ${groups.length} ACCOUNTNO grubu bulundu.`);
  }

  return {
    orderCsv: groups[0].orderCsv,
    stockCsv: groups[0].stockCsv,
    stats
  };
}

export function annotateRowsWithAccount(rows, accountNo) {
  return (rows || []).map((row) => ({
    ...row,
    ACCOUNTNO: makeAccountLabel(accountNo),
    PICKER_ID: row.PICKER_ID ? `${row.PICKER_ID}_${makeAccountLabel(accountNo)}` : row.PICKER_ID,
    PICKCAR_ID: row.PICKCAR_ID ? `${row.PICKCAR_ID}_${makeAccountLabel(accountNo)}` : row.PICKCAR_ID
  }));
}

export function aggregateSolverSummaries(summaries, stats) {
  const normalized = summaries.filter(Boolean);
  if (normalized.length === 0) return null;
  if (normalized.length === 1) {
    return {
      ...normalized[0],
      account_count: stats?.accountCount || 1,
      account_groups: stats?.accountGroups || []
    };
  }

  return {
    algorithm: normalized.map((summary) => summary.algorithm).filter(Boolean).join(' + '),
    orders: 'ACCOUNTNO grouped orders',
    stock: 'ACCOUNTNO grouped stock',
    objective_value: normalized.reduce((sum, summary) => sum + Number(summary.objective_value || 0), 0),
    distance: normalized.reduce((sum, summary) => sum + Number(summary.distance || 0), 0),
    floors: normalized.reduce((sum, summary) => sum + Number(summary.floors || 0), 0),
    thms: normalized.reduce((sum, summary) => sum + Number(summary.thms || 0), 0),
    pick_rows: normalized.reduce((sum, summary) => sum + Number(summary.pick_rows || 0), 0),
    visited_nodes: normalized.reduce((sum, summary) => sum + Number(summary.visited_nodes || 0), 0),
    solve_time: normalized.reduce((sum, summary) => sum + Number(summary.solve_time || 0), 0),
    account_count: stats?.accountCount || normalized.length,
    account_groups: stats?.accountGroups || [],
    notes: {
      account_grouping: 'ACCOUNTNO',
      account_count: String(stats?.accountCount || normalized.length)
    }
  };
}

function clampNumber(value, min, max, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

export function resolveSolverOptions(body = {}) {
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
    timeLimit: clampNumber(body.timeLimit, 1, 600, 120)
  };
}

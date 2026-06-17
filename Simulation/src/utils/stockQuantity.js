export const STOCK_FORMULAS = {
  thm: 'QTY_STOCK - QTY_STOCK_OUT_PLANNED + QTY_STOCK_IN_PLANNED',
  allocation: 'QTY_STOCK - QTY_STOCK_OUT_PLANNED'
};

const BASE_STOCK_COLUMNS = ['Stok', 'STOCK', 'STOCK_AMOUNT', 'QTY_STOCK'];
const PLANNED_IN_COLUMNS = ['QTY_STOCK_IN_PLANNED', 'STOCK_IN_PLANNED', 'IN_PLANNED', 'Rezerve', 'RESERVED'];
const PLANNED_OUT_COLUMNS = ['QTY_STOCK_OUT_PLANNED', 'STOCK_OUT_PLANNED', 'OUT_PLANNED'];

function firstPresentValue(row, names) {
  for (const name of names) {
    if (!Object.prototype.hasOwnProperty.call(row, name)) continue;
    const value = row[name];
    if (value === undefined || value === null) continue;
    if (String(value).trim() !== '') return value;
  }

  return '';
}

function toStockInteger(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.trunc(value);
  }

  const text = String(value ?? '').trim().replace(',', '.');
  if (!text) return 0;

  const parsed = Number.parseFloat(text);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : 0;
}

export function getStockQuantityComponents(row = {}) {
  return {
    qtyStock: toStockInteger(firstPresentValue(row, BASE_STOCK_COLUMNS)),
    plannedIn: toStockInteger(firstPresentValue(row, PLANNED_IN_COLUMNS)),
    plannedOut: toStockInteger(firstPresentValue(row, PLANNED_OUT_COLUMNS))
  };
}

export function calculateStockQuantity(row = {}, { includePlannedIn = true, clampZero = true } = {}) {
  const { qtyStock, plannedIn, plannedOut } = getStockQuantityComponents(row);
  const stock = qtyStock - plannedOut + (includePlannedIn ? plannedIn : 0);

  return clampZero ? Math.max(0, stock) : stock;
}

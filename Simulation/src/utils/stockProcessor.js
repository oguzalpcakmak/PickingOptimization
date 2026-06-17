import { calculateStockQuantity, getStockQuantityComponents } from './stockQuantity.js';

/**
 * Processes the "Stok Bilgisi" sheet and merges it with pick results.
 */

export function transformStockRow(row) {
  const toString = (val) => (val !== undefined && val !== null ? String(val) : '');
  const stripLeadingZeros = (val) => {
    const text = toString(val).trim();
    if (!/^\d+$/.test(text)) return text;
    return String(parseInt(text, 10));
  };
  const { qtyStock, plannedIn, plannedOut } = getStockQuantityComponents(row);

  return {
    ACCOUNTNO: toString(row['ACCOUNTNO']),
    PICKED_THM: toString(row['THM_ID']),
    ARTICLE_CODE: toString(row['ARTICLE_CODE']),
    AREA: toString(row['ACT_AREA']),
    AISLE: stripLeadingZeros(row['ACT_AISLE']),
    COLUMN: stripLeadingZeros(row['ACT_X']),
    SHELF: stripLeadingZeros(row['ACT_Y']),
    LEFT_OR_RIGHT: toString(row['ACT_Z']),
    STOCK: calculateStockQuantity(row),
    RESERVED: plannedIn,
    QTY_STOCK: qtyStock,
    QTY_STOCK_IN_PLANNED: plannedIn,
    QTY_STOCK_OUT_PLANNED: plannedOut
  };
}

export function processStockData(rawStockData) {
  return rawStockData.map((row) => transformStockRow(row));
}

/**
 * Adds picked quantities back because the stock sheet usually represents
 * post-pick state.
 */
export function mergeStockWithPicks(stockData, pickData) {
  const stockMap = new Map();

  for (const stock of stockData) {
    const key = `${stock.ACCOUNTNO || ''}|${stock.PICKED_THM}|${stock.ARTICLE_CODE}`;
    stockMap.set(key, { ...stock });
  }

  const pickQuantities = new Map();

  for (const pick of pickData) {
    const key = `${pick.ACCOUNTNO || ''}|${pick.PICKED_THM}|${pick.ARTICLE_CODE}`;
    const amount = parseInt(pick.PICKED_AMOUNT, 10) || 1;

    if (!pickQuantities.has(key)) {
      pickQuantities.set(key, {
        totalPicked: 0,
        ACCOUNTNO: pick.ACCOUNTNO || '',
        AREA: pick.AREA,
        AISLE: pick.AISLE,
        COLUMN: pick.COLUMN,
        SHELF: pick.SHELF,
        LEFT_OR_RIGHT: pick.LEFT_OR_RIGHT
      });
    }
    pickQuantities.get(key).totalPicked += amount;
  }

  let updatedCount = 0;
  let newStockCount = 0;
  let totalAddedBack = 0;

  for (const [key, pickInfo] of pickQuantities) {
    const [accountNo, thm, article] = key.split('|');

    if (stockMap.has(key)) {
      const stockItem = stockMap.get(key);
      stockItem.STOCK += pickInfo.totalPicked;
      totalAddedBack += pickInfo.totalPicked;
      updatedCount++;
    } else {
      stockMap.set(key, {
        ACCOUNTNO: accountNo,
        PICKED_THM: thm,
        ARTICLE_CODE: article,
        AREA: pickInfo.AREA,
        AISLE: pickInfo.AISLE,
        COLUMN: pickInfo.COLUMN,
        SHELF: pickInfo.SHELF,
        LEFT_OR_RIGHT: pickInfo.LEFT_OR_RIGHT,
        STOCK: pickInfo.totalPicked,
        RESERVED: 0,
        QTY_STOCK: 0,
        QTY_STOCK_IN_PLANNED: 0,
        QTY_STOCK_OUT_PLANNED: 0
      });
      totalAddedBack += pickInfo.totalPicked;
      newStockCount++;
    }
  }

  const updatedStock = Array.from(stockMap.values()).sort((a, b) => {
    const accountComp = String(a.ACCOUNTNO || '').localeCompare(String(b.ACCOUNTNO || ''));
    if (accountComp !== 0) return accountComp;

    const areaComp = String(a.AREA || '').localeCompare(String(b.AREA || ''));
    if (areaComp !== 0) return areaComp;

    const aisleA = parseInt(a.AISLE, 10) || 0;
    const aisleB = parseInt(b.AISLE, 10) || 0;
    if (aisleA !== aisleB) return aisleA - aisleB;

    const colA = parseInt(a.COLUMN, 10) || 0;
    const colB = parseInt(b.COLUMN, 10) || 0;
    return colA - colB;
  });

  const stats = {
    originalStockCount: stockData.length,
    totalPickItems: pickQuantities.size,
    updatedCount,
    newStockCount,
    finalStockCount: updatedStock.length,
    totalAddedBack
  };

  return { data: updatedStock, stats };
}

export function stockToCSV(data) {
  if (!data || data.length === 0) {
    return '';
  }

  const headers = [
    'ACCOUNTNO',
    'PICKED_THM',
    'ARTICLE_CODE',
    'AREA',
    'AISLE',
    'COLUMN',
    'SHELF',
    'LEFT_OR_RIGHT',
    'STOCK',
    'RESERVED',
    'QTY_STOCK',
    'QTY_STOCK_IN_PLANNED',
    'QTY_STOCK_OUT_PLANNED'
  ];

  const rows = data.map((row) => headers.map((h) => (row[h] !== undefined ? row[h] : '')).join(';'));

  return [headers.join(';'), ...rows].join('\n');
}

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const simulationDir = path.resolve(__dirname, '..');
const repoRoot = path.resolve(simulationDir, '..');
const outputDir = path.join(simulationDir, 'public', 'test-fixtures');
const selectedArticles = new Set(['567', '577', '606', '609', '699']);

function readCsv(relativePath) {
  return Papa.parse(fs.readFileSync(path.join(repoRoot, relativePath), 'utf8').replace(/^\uFEFF/, ''), {
    header: true,
    skipEmptyLines: true
  }).data;
}

const allOrders = readCsv('data/full/PickOrder.csv');
const allStock = readCsv('data/full/StockData.csv');
const firstStockByArticle = new Map();

for (const row of allStock) {
  if (!firstStockByArticle.has(String(row.ARTICLE_CODE))) {
    firstStockByArticle.set(String(row.ARTICLE_CODE), row);
  }
}

function writeFixture(filename, orders, stock) {
  const pickRows = orders.map((order, index) => {
    const location = firstStockByArticle.get(String(order.ARTICLE_CODE));
    if (!location) throw new Error(`Stock row not found for article ${order.ARTICLE_CODE}`);

    return {
      'Kullanıcı Kodu': 'WASM_TEST',
      TOPLANAN_THM: location.THM_ID,
      ARTICLE_CODE: Number(order.ARTICLE_CODE),
      DATE_START_EXECUTION: '05.31.2026 10:00 AM',
      AREA: location.FLOOR,
      AISLE: Number(location.AISLE),
      X: Number(location.COLUMN),
      Y: Number(location.SHELF),
      Z: location.LEFT_OR_RIGHT,
      TOPLANAN_ADET: Number(order.AMOUNT),
      PICKCAR_THM: `PC_${String(index + 1).padStart(4, '0')}`
    };
  });

  const stockRows = stock.map((row) => ({
    THM_ID: row.THM_ID,
    ARTICLE_CODE: Number(row.ARTICLE_CODE),
    ACT_AREA: row.FLOOR,
    ACT_AISLE: Number(row.AISLE),
    ACT_X: Number(row.COLUMN),
    ACT_Y: Number(row.SHELF),
    ACT_Z: row.LEFT_OR_RIGHT,
    Stok: Number(row.STOCK),
    Rezerve: 0
  }));

  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(pickRows), 'Grup Toplama Verisi');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(stockRows), 'Stok Bilgisi');

  const outputPath = path.join(outputDir, filename);
  XLSX.writeFile(workbook, outputPath);
  console.log(`Created ${outputPath}`);
}

fs.mkdirSync(outputDir, { recursive: true });
writeFixture(
  'solver-small.xlsx',
  allOrders.filter((row) => selectedArticles.has(String(row.ARTICLE_CODE))),
  allStock.filter((row) => selectedArticles.has(String(row.ARTICLE_CODE)))
);
if (process.argv.includes('--full')) {
  writeFixture('solver-full.xlsx', allOrders, allStock);
}

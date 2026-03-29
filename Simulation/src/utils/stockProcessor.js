/**
 * Stok verisi işleme fonksiyonları
 * "Stok Bilgisi" sheet'ini işler ve toplama verileriyle birleştirir
 */

/**
 * Stok Bilgisi satırını dönüştürür
 * @param {Object} row - Orijinal Excel satırı
 * @returns {Object} Dönüştürülmüş satır
 */
export function transformStockRow(row) {
  const toString = (val) => val !== undefined && val !== null ? String(val) : '';
  const toNumber = (val) => {
    const num = parseInt(val, 10);
    return isNaN(num) ? 0 : num;
  };

  return {
    PICKED_THM: toString(row['THM_ID']),
    ARTICLE_CODE: toString(row['ARTICLE_CODE']),
    AREA: toString(row['ACT_AREA']),
    AISLE: toString(row['ACT_AISLE']),
    COLUMN: toString(row['ACT_X']),
    SHELF: toString(row['ACT_Y']),
    LEFT_OR_RIGHT: toString(row['ACT_Z']),
    STOCK: toNumber(row['Stok']),
    RESERVED: toNumber(row['Rezerve'])
  };
}

/**
 * Excel'den gelen stok verilerini işler
 * @param {Array} rawStockData - Ham stok verileri
 * @returns {Array} Dönüştürülmüş stok verileri
 */
export function processStockData(rawStockData) {
  return rawStockData.map(row => transformStockRow(row));
}

/**
 * Stok verisini toplama verisiyle birleştirir ve günceller
 * Toplanan miktarları stoğa geri ekler çünkü mevcut veri toplamadan sonraki stok
 * @param {Array} stockData - İşlenmiş stok verileri
 * @param {Array} pickData - İşlenmiş toplama verileri
 * @returns {Object} Güncellenmiş stok verileri ve istatistikler
 */
export function mergeStockWithPicks(stockData, pickData) {
  // Stok verisini Map'e dönüştür (key: PICKED_THM|ARTICLE_CODE)
  const stockMap = new Map();
  
  for (const stock of stockData) {
    const key = `${stock.PICKED_THM}|${stock.ARTICLE_CODE}`;
    stockMap.set(key, { ...stock });
  }

  // Toplama verilerini grupla ve toplam miktarları hesapla
  const pickQuantities = new Map();
  
  for (const pick of pickData) {
    const key = `${pick.PICKED_THM}|${pick.ARTICLE_CODE}`;
    const amount = parseInt(pick.PICKED_AMOUNT) || 1;
    
    if (!pickQuantities.has(key)) {
      pickQuantities.set(key, {
        totalPicked: 0,
        // Stokta yoksa konum bilgisini toplama verisinden al
        AREA: pick.AREA,
        AISLE: pick.AISLE,
        COLUMN: pick.COLUMN,
        SHELF: pick.SHELF,
        LEFT_OR_RIGHT: pick.LEFT_OR_RIGHT
      });
    }
    pickQuantities.get(key).totalPicked += amount;
  }

  // İstatistikler
  let updatedCount = 0;
  let newStockCount = 0;
  let totalAddedBack = 0;

  // Toplanan miktarları stoğa geri ekle
  for (const [key, pickInfo] of pickQuantities) {
    const [thm, article] = key.split('|');
    
    if (stockMap.has(key)) {
      // Mevcut stok kaydını güncelle
      const stockItem = stockMap.get(key);
      stockItem.STOCK += pickInfo.totalPicked;
      totalAddedBack += pickInfo.totalPicked;
      updatedCount++;
    } else {
      // Yeni stok kaydı oluştur (stok bitmiş ürünler)
      stockMap.set(key, {
        PICKED_THM: thm,
        ARTICLE_CODE: article,
        AREA: pickInfo.AREA,
        AISLE: pickInfo.AISLE,
        COLUMN: pickInfo.COLUMN,
        SHELF: pickInfo.SHELF,
        LEFT_OR_RIGHT: pickInfo.LEFT_OR_RIGHT,
        STOCK: pickInfo.totalPicked,
        RESERVED: 0
      });
      totalAddedBack += pickInfo.totalPicked;
      newStockCount++;
    }
  }

  // Map'i array'e dönüştür ve sırala
  const updatedStock = Array.from(stockMap.values()).sort((a, b) => {
    // AREA'ya göre sırala
    const areaComp = a.AREA.localeCompare(b.AREA);
    if (areaComp !== 0) return areaComp;
    
    // AISLE'a göre sırala
    const aisleA = parseInt(a.AISLE) || 0;
    const aisleB = parseInt(b.AISLE) || 0;
    if (aisleA !== aisleB) return aisleA - aisleB;
    
    // COLUMN'a göre sırala
    const colA = parseInt(a.COLUMN) || 0;
    const colB = parseInt(b.COLUMN) || 0;
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

/**
 * Güncellenmiş stok verisini CSV formatına çevirir
 * @param {Array} data - Güncellenmiş stok verileri
 * @returns {string} CSV string
 */
export function stockToCSV(data) {
  if (!data || data.length === 0) {
    return '';
  }

  const headers = [
    'PICKED_THM', 'ARTICLE_CODE', 'AREA', 'AISLE', 
    'COLUMN', 'SHELF', 'LEFT_OR_RIGHT', 'STOCK', 'RESERVED'
  ];

  const rows = data.map(row => 
    headers.map(h => row[h] !== undefined ? row[h] : '').join(';')
  );

  return [headers.join(';'), ...rows].join('\n');
}

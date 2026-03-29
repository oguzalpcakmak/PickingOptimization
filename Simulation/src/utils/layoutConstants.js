/**
 * Depo Layout Sabitleri
 * Tüm ölçüler metre cinsinden
 */

// Temel ölçüler
export const AISLE_WIDTH = 1.36;        // Koridor genişliği
export const COLUMN_LENGTH = 2.90;      // Raf sütunu uzunluğu
export const SHELF_DEPTH = 1.16;        // Raf derinliği
export const CROSS_AISLE_WIDTH = 2.70;  // Cross aisle genişliği

// Layout boyutları
export const TOTAL_AISLES = 27;
export const TOTAL_COLUMNS = 20;

// Asansör konumları (Cross Aisle 1'in dışına bitişik)
export const ELEVATOR_1_AISLE = 8;   // 1. asansör 8. koridor hizasında
export const ELEVATOR_2_AISLE = 18;  // 2. asansör 18. koridor hizasında
export const ELEVATOR_WIDTH = AISLE_WIDTH;  // Asansör genişliği (koridor genişliği kadar)
export const ELEVATOR_DEPTH = 1.5;   // Asansör derinliği

// Merdiven tanımları
// Cross Aisle 1'e çıkan merdivenler (y = CROSS_AISLE_WIDTH, shelf bitişiği)
// Cross Aisle 2'ye çıkan merdivenler (y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH, shelf bitişiği)
export const STAIRS = [
  { id: 1, aisle1: 5,  aisle2: 6,  crossAisle: 1 },  // STAIR 1: 5-6 arası, CA1
  { id: 2, aisle1: 15, aisle2: 16, crossAisle: 1 },  // STAIR 2: 15-16 arası, CA1
  { id: 3, aisle1: 24, aisle2: 25, crossAisle: 1 },  // STAIR 3: 24-25 arası, CA1
  { id: 4, aisle1: 9,  aisle2: 10, crossAisle: 2 },  // STAIR 4: 9-10 arası, CA2
  { id: 5, aisle1: 19, aisle2: 20, crossAisle: 2 },  // STAIR 5: 19-20 arası, CA2
  { id: 6, aisle1: 4,  aisle2: 5,  crossAisle: 3 },  // STAIR 6: 4-5 arası, CA3
  { id: 7, aisle1: 14, aisle2: 15, crossAisle: 3 },  // STAIR 7: 14-15 arası, CA3
  { id: 8, aisle1: 23, aisle2: 24, crossAisle: 3 },  // STAIR 8: 23-24 arası, CA3
];

export const STAIR_WIDTH = AISLE_WIDTH;   // Merdiven genişliği
export const STAIR_DEPTH = 1.5;           // Merdiven derinliği

// Geçerli arealar
export const VALID_AREAS = new Set(['MZN1', 'MZN2', 'MZN3', 'MZN4', 'MZN5', 'MZN6']);

// Hesaplanmış değerler
export const LAYOUT_WIDTH = SHELF_DEPTH + AISLE_WIDTH + (TOTAL_AISLES - 1) * (AISLE_WIDTH + 2 * SHELF_DEPTH) + SHELF_DEPTH;
export const LAYOUT_HEIGHT = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH;

// Cross aisle Y pozisyonları
export const CROSS_AISLE_1_Y = CROSS_AISLE_WIDTH / 2;
export const CROSS_AISLE_2_Y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH / 2;
export const CROSS_AISLE_3_Y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH / 2;

// Tolerans değerleri
export const POSITION_TOLERANCE = 0.01;

/**
 * AISLE numarasını görsel indekse çevirir (sağdan sola: AISLE 27 solda, AISLE 1 sağda)
 * @param {number} aisle - AISLE numarası (1-27)
 * @returns {number} Görsel indeks (1-27, ters çevrilmiş)
 */
export function getReversedAisleIndex(aisle) {
  return TOTAL_AISLES - aisle + 1;
}

/**
 * Asansör pozisyonunu hesaplar (görselleştirme için)
 * @param {number} elevatorNum - Asansör numarası (1 veya 2)
 * @returns {{x: number, y: number}} Asansör merkez koordinatları
 */
export function getElevatorPosition(elevatorNum) {
  const aisle = elevatorNum === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
  return {
    x: getXCoordinate(aisle),
    y: -ELEVATOR_DEPTH / 2  // Cross aisle 1'in dışında (üstte)
  };
}

/**
 * Verilen aisle'a en yakın asansörü belirler
 * @param {number} targetAisle - Hedef aisle numarası
 * @returns {number} En yakın asansör numarası (1 veya 2)
 */
export function getNearestElevator(targetAisle) {
  const distTo1 = Math.abs(targetAisle - ELEVATOR_1_AISLE);
  const distTo2 = Math.abs(targetAisle - ELEVATOR_2_AISLE);
  return distTo1 <= distTo2 ? 1 : 2;
}

/**
 * Asansörden hedef pozisyona mesafeyi hesaplar
 * Cross aisle boyunca yatay mesafe: |aisle_farkı| * (AISLE_WIDTH + 2*SHELF_DEPTH)
 *   - Her aisle geçişinde: koridor genişliği + 2 raf derinliği (R + L raflar)
 * Dikey mesafe: CROSS_AISLE_WIDTH + (column - 0.5) * COLUMN_LENGTH (column 1-10 için)
 * 
 * @param {number} elevatorAisle - Asansör aisle numarası
 * @param {number} targetAisle - Hedef aisle numarası
 * @param {number} targetColumn - Hedef column numarası
 * @returns {number} Mesafe (metre)
 */
export function getElevatorToPickDistance(elevatorAisle, targetAisle, targetColumn) {
  // Yatay mesafe: Cross aisle boyunca koridor genişlikleri + raf derinlikleri
  // Her aisle geçişi = AISLE_WIDTH + 2*SHELF_DEPTH (bir R raf + bir L raf)
  const horizontalDist = Math.abs(targetAisle - elevatorAisle) * (AISLE_WIDTH + 2 * SHELF_DEPTH);
  
  // Dikey mesafe
  let verticalDist;
  if (targetColumn <= 10) {
    // Column 1-10: Cross aisle 1'den giriş
    verticalDist = CROSS_AISLE_WIDTH + (targetColumn - 0.5) * COLUMN_LENGTH;
  } else {
    // Column 11-20: Cross aisle 1'den giriş, cross aisle 2'den geçiş
    // Cross aisle 1 -> column 10 sonu -> cross aisle 2 -> hedef column
    verticalDist = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + (targetColumn - 10 - 0.5) * COLUMN_LENGTH;
  }
  
  return horizontalDist + verticalDist;
}

/**
 * X koordinatını hesaplar (AISLE bazlı) - Sağdan sola sıralama
 * AISLE 27 en solda, AISLE 1 en sağda
 * @param {number} aisle - AISLE numarası (1-27)
 * @returns {number} X koordinatı (metre)
 */
export function getXCoordinate(aisle) {
  const reversedAisle = getReversedAisleIndex(aisle);
  if (reversedAisle === 1) {
    return SHELF_DEPTH + AISLE_WIDTH / 2;
  }
  const aisle1Center = SHELF_DEPTH + AISLE_WIDTH / 2;
  return aisle1Center + (reversedAisle - 1) * (AISLE_WIDTH + 2 * SHELF_DEPTH);
}

/**
 * Y koordinatını hesaplar (COLUMN bazlı)
 * @param {number} column - COLUMN numarası (1-20)
 * @returns {number} Y koordinatı (metre)
 */
export function getYCoordinate(column) {
  if (column <= 10) {
    return CROSS_AISLE_WIDTH + (column - 0.5) * COLUMN_LENGTH;
  }
  const crossAisle2Start = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH;
  const colInSecondHalf = column - 10;
  return crossAisle2Start + CROSS_AISLE_WIDTH + (colInSecondHalf - 0.5) * COLUMN_LENGTH;
}

/**
 * Pozisyon koordinatlarını hesaplar
 * @param {number} aisle - AISLE numarası
 * @param {number} column - COLUMN numarası
 * @returns {{x: number, y: number}} Koordinatlar
 */
export function getPosition(aisle, column) {
  return {
    x: getXCoordinate(aisle),
    y: getYCoordinate(column)
  };
}

/**
 * İki nokta arasındaki Manhattan yolunu hesaplar (CROSS_AISLE'lardan geçerek)
 * @param {number} x1 - Başlangıç X
 * @param {number} y1 - Başlangıç Y
 * @param {number} x2 - Bitiş X
 * @param {number} y2 - Bitiş Y
 * @returns {Array<{x: number, y: number}>} Yol noktaları
 */
export function getManhattanPath(x1, y1, x2, y2) {
  // Aynı AISLE'da ise direkt dikey çizgi
  if (Math.abs(x1 - x2) < POSITION_TOLERANCE) {
    return [
      { x: x1, y: y1 },
      { x: x2, y: y2 }
    ];
  }

  // En uygun CROSS_AISLE'ı bul
  const crossAisles = [CROSS_AISLE_1_Y, CROSS_AISLE_2_Y, CROSS_AISLE_3_Y];
  
  let bestCrossAisle = crossAisles[0];
  let minDistance = Infinity;

  for (const caY of crossAisles) {
    const dist = Math.abs(y1 - caY) + Math.abs(x1 - x2) + Math.abs(caY - y2);
    if (dist < minDistance) {
      minDistance = dist;
      bestCrossAisle = caY;
    }
  }

  // Yol: başlangıç -> cross aisle -> yatay hareket -> hedef
  return [
    { x: x1, y: y1 },             // Başlangıç
    { x: x1, y: bestCrossAisle }, // Cross aisle'a in/çık
    { x: x2, y: bestCrossAisle }, // Cross aisle boyunca yatay
    { x: x2, y: y2 }              // Hedef
  ];
}

/**
 * Manhattan mesafesini CROSS_AISLE kısıtlamasıyla hesaplar
 * @param {{x: number, y: number}} pos1 - Başlangıç pozisyonu
 * @param {{x: number, y: number}} pos2 - Bitiş pozisyonu
 * @returns {number} Mesafe (metre)
 */
export function manhattanDistanceWithCrossAisles(pos1, pos2) {
  const { x: x1, y: y1 } = pos1;
  const { x: x2, y: y2 } = pos2;

  // Aynı AISLE'daysa direkt Manhattan
  if (Math.abs(x1 - x2) < POSITION_TOLERANCE) {
    return Math.abs(y1 - y2);
  }

  const crossAisles = [CROSS_AISLE_1_Y, CROSS_AISLE_2_Y, CROSS_AISLE_3_Y];

  let minDistance = Infinity;

  for (const caY of crossAisles) {
    const distToCaFrom1 = Math.abs(y1 - caY);
    const distAlongCa = Math.abs(x1 - x2);
    const distTo2FromCa = Math.abs(caY - y2);

    const totalDist = distToCaFrom1 + distAlongCa + distTo2FromCa;
    minDistance = Math.min(minDistance, totalDist);
  }

  return minDistance;
}

/**
 * Merdiven pozisyonunu hesaplar
 * @param {number} stairId - Merdiven ID'si (1-8)
 * @returns {{x: number, y: number, crossAisle: number}} Merdiven koordinatları
 */
export function getStairPosition(stairId) {
  const stair = STAIRS.find(s => s.id === stairId);
  if (!stair) return null;
  
  // X: İki koridorun tam ortası
  const x1 = getXCoordinate(stair.aisle1);
  const x2 = getXCoordinate(stair.aisle2);
  const x = (x1 + x2) / 2;
  
  // Y: Cross aisle'a göre (shelf tarafına bitişik)
  let y;
  if (stair.crossAisle === 1) {
    // Cross Aisle 1'in bittiği yer (column 1'in başladığı yer)
    y = CROSS_AISLE_WIDTH;
  } else if (stair.crossAisle === 2) {
    // Cross Aisle 2'nin başladığı yer (column 10'un bittiği yer)
    y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH;
  } else {
    // Cross Aisle 3'ün başladığı yer (column 20'nin bittiği yer)
    y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH;
  }
  
  return { x, y, crossAisle: stair.crossAisle };
}

/**
 * Verilen asansöre en yakın merdiveni bulur
 * @param {number} elevatorNum - Asansör numarası (1 veya 2)
 * @returns {number} En yakın merdiven ID'si
 */
export function getNearestStairToElevator(elevatorNum) {
  const elevatorAisle = elevatorNum === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
  const elevatorX = getXCoordinate(elevatorAisle);
  
  let nearestStair = 1;
  let minDist = Infinity;
  
  for (const stair of STAIRS) {
    // Sadece Cross Aisle 1'deki merdivenler asansöre yakın (asansörler CA1'de)
    if (stair.crossAisle !== 1) continue;
    
    const stairPos = getStairPosition(stair.id);
    const dist = Math.abs(stairPos.x - elevatorX);
    
    if (dist < minDist) {
      minDist = dist;
      nearestStair = stair.id;
    }
  }
  
  return nearestStair;
}

/**
 * Merdivenden asansöre mesafeyi hesaplar
 * @param {number} stairId - Merdiven ID'si
 * @param {number} elevatorNum - Asansör numarası
 * @returns {number} Mesafe (metre)
 */
export function getStairToElevatorDistance(stairId, elevatorNum) {
  const stairPos = getStairPosition(stairId);
  const elevatorAisle = elevatorNum === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
  const elevatorX = getXCoordinate(elevatorAisle);
  
  // Yatay mesafe (Cross Aisle 1 boyunca)
  const horizontalDist = Math.abs(stairPos.x - elevatorX);
  
  // Dikey mesafe (merdivenin Y konumundan Cross Aisle 1 ortasına)
  // Merdiven CA1 shelf bitişiğinde (y = CROSS_AISLE_WIDTH)
  // Asansör CA1'in dışında (y ≈ 0)
  // Fark: CROSS_AISLE_WIDTH
  const verticalDist = stairPos.crossAisle === 1 ? CROSS_AISLE_WIDTH : 0;
  
  return horizontalDist + verticalDist;
}

/**
 * Verilen pozisyona en yakın merdiveni bulur
 * (genellikle asansör pozisyonuna göre kullanılır)
 * @param {number} aisle - Aisle numarası
 * @returns {{stairId: number, distance: number}} En yakın merdiven ve mesafesi
 */
export function getNearestStair(aisle) {
  const x = getXCoordinate(aisle);
  
  let nearestStair = 1;
  let minDist = Infinity;
  
  // Sadece Cross Aisle 1'deki merdivenler (asansörler CA1'de olduğu için)
  for (const stair of STAIRS) {
    if (stair.crossAisle !== 1) continue;
    
    const stairPos = getStairPosition(stair.id);
    const dist = Math.abs(stairPos.x - x);
    
    if (dist < minDist) {
      minDist = dist;
      nearestStair = stair.id;
    }
  }
  
  return { stairId: nearestStair, distance: minDist };
}

import {
  AISLE_WIDTH,
  COLUMN_LENGTH,
  SHELF_DEPTH,
  CROSS_AISLE_WIDTH,
  VALID_AREAS,
  CROSS_AISLE_1_Y,
  CROSS_AISLE_2_Y,
  CROSS_AISLE_3_Y,
  POSITION_TOLERANCE,
  getPosition,
  manhattanDistanceWithCrossAisles,
  ELEVATOR_1_AISLE,
  ELEVATOR_2_AISLE,
  getNearestElevator,
  getElevatorToPickDistance,
  getNearestStairToElevator,
  getStairToElevatorDistance
} from './layoutConstants.js';

/**
 * Amerikan tarih formatını (MM.DD.YYYY HH:MM AM/PM) Türk formatına dönüştürür.
 * @param {string} dateStr - Amerikan formatında tarih string'i
 * @returns {{date: string, time: string}} Türk formatında tarih ve saat
 */
export function transformDateTime(dateStr) {
  if (!dateStr || dateStr.trim() === '') {
    return { date: '', time: '' };
  }

  const str = dateStr.trim();
  
  // Farklı formatları dene
  const formats = [
    // MM.DD.YYYY HH:MM AM/PM
    /^(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)$/i,
    // MM.DD.YYYY HH:MMAM/PM (boşluksuz)
    /^(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})(AM|PM)$/i,
    // MM/DD/YYYY HH:MM AM/PM
    /^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)$/i,
    // Sadece tarih: MM.DD.YYYY
    /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/,
    // Sadece tarih: MM/DD/YYYY
    /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/,
  ];

  for (const regex of formats) {
    const match = str.match(regex);
    if (match) {
      const month = match[1].padStart(2, '0');
      const day = match[2].padStart(2, '0');
      const year = match[3];
      
      // Türk formatı: DD.MM.YYYY
      const dateTurkish = `${day}.${month}.${year}`;
      
      // Saat bilgisi varsa
      if (match.length >= 7) {
        let hours = parseInt(match[4], 10);
        const minutes = match[5];
        const ampm = match[6].toUpperCase();
        
        // 12 saat formatından 24 saat formatına
        if (ampm === 'PM' && hours !== 12) {
          hours += 12;
        } else if (ampm === 'AM' && hours === 12) {
          hours = 0;
        }
        
        const time24h = `${hours.toString().padStart(2, '0')}:${minutes}`;
        return { date: dateTurkish, time: time24h };
      }
      
      return { date: dateTurkish, time: '' };
    }
  }

  console.warn(`Tarih dönüştürme hatası: ${dateStr}`);
  return { date: dateStr, time: '' };
}

/**
 * Excel satırını dönüştürür (transform_csv.py işlevselliği)
 * @param {Object} row - Orijinal Excel satırı
 * @returns {Object} Dönüştürülmüş satır
 */
export function transformRow(row) {
  const { date, time } = transformDateTime(row['DATE_START_EXECUTION']);
  
  // Excel'den gelen değerleri string'e çevir
  const toString = (val) => val !== undefined && val !== null ? String(val) : '';
  
  return {
    'PICKER_CODE': toString(row['Kullanıcı Kodu']),
    'PICKCAR_THM': toString(row['PICKCAR_THM']),
    'DATE': date,
    'TIME': time,
    'AREA': toString(row['AREA']),
    'AISLE': toString(row['AISLE']),
    'COLUMN': toString(row['X']),
    'SHELF': toString(row['Y']),
    'LEFT_OR_RIGHT': toString(row['Z']),
    'PICKED_THM': toString(row['TOPLANAN_THM']),
    'ARTICLE_CODE': toString(row['ARTICLE_CODE']),
    'PICKED_AMOUNT': toString(row['TOPLANAN_ADET'])
  };
}

/**
 * Saat stringini dakikaya çevirir
 * @param {string} timeStr - Saat string'i (HH:MM)
 * @returns {number|null} Dakika cinsinden saat
 */
function parseTime(timeStr) {
  if (!timeStr || timeStr.trim() === '') {
    return null;
  }
  const parts = timeStr.trim().split(':');
  if (parts.length === 2) {
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
  }
  return null;
}

/**
 * İki pick arasındaki mesafeyi hesaplar
 * İlk pick için en yakın asansörden mesafe hesaplanır
 * @param {Object|null} prevPick - Önceki pick (ilk pick için null)
 * @param {Object} currPick - Mevcut pick
 * @returns {number} Mesafe (metre)
 */
function calculateStepDistance(prevPick, currPick) {
  const currAisle = parseInt(currPick.AISLE);
  const currColumn = parseInt(currPick.COLUMN);
  
  if (!prevPick) {
    // İlk pick: En yakın asansörden mesafe hesapla
    const nearestElevator = getNearestElevator(currAisle);
    const elevatorAisle = nearestElevator === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
    return getElevatorToPickDistance(elevatorAisle, currAisle, currColumn);
  }

  // Aynı AISLE ve COLUMN kontrolü
  if (parseInt(prevPick.AISLE) === currAisle &&
      parseInt(prevPick.COLUMN) === currColumn) {
    return 0;
  }

  return manhattanDistanceWithCrossAisles(prevPick.position, currPick.position);
}

/**
 * Bir toplama grubunun sırasını belirler
 * @param {Array} picks - Toplama listesi
 * @returns {Array} Sıralanmış ve mesafe hesaplanmış liste
 */
function determinePickOrder(picks) {
  if (!picks || picks.length === 0) {
    return [];
  }

  // Her pick'e pozisyon ve zaman bilgisi ekle
  for (const pick of picks) {
    pick.position = getPosition(parseInt(pick.AISLE), parseInt(pick.COLUMN));
    pick.timeMinutes = parseTime(pick.TIME);
  }

  // TIME bilgisi olan ve olmayan pick'leri ayır
  const picksWithTime = picks.filter(p => p.timeMinutes !== null);
  const picksWithoutTime = picks.filter(p => p.timeMinutes === null);

  if (picksWithTime.length === 0) {
    // Hiç TIME bilgisi yoksa pozisyona göre sırala
    const sortedPicks = [...picks].sort((a, b) => {
      const aisleDiff = parseInt(a.AISLE) - parseInt(b.AISLE);
      if (aisleDiff !== 0) return aisleDiff;
      return parseInt(a.COLUMN) - parseInt(b.COLUMN);
    });
    sortedPicks.forEach((pick, i) => {
      pick.PICK_ORDER = i + 1;
    });
    return sortedPicks;
  }

  // TIME bazlı grupla
  const timeGroups = new Map();
  for (const pick of picksWithTime) {
    const key = pick.timeMinutes;
    if (!timeGroups.has(key)) {
      timeGroups.set(key, []);
    }
    timeGroups.get(key).push(pick);
  }

  // Sıralı zamanları al
  const sortedTimes = [...timeGroups.keys()].sort((a, b) => a - b);

  // Sonuç listesi
  const orderedPicks = [];
  let currentOrder = 1;
  let lastPosition = null;

  for (const timeMinute of sortedTimes) {
    const group = timeGroups.get(timeMinute);

    if (group.length === 1) {
      group[0].PICK_ORDER = currentOrder;
      orderedPicks.push(group[0]);
      lastPosition = group[0].position;
      currentOrder++;
    } else {
      // Birden fazla ürün aynı dakikada
      let remaining = [...group];

      if (lastPosition === null) {
        // İlk grup, en düşük AISLE ve COLUMN'dan başla
        remaining.sort((a, b) => {
          const aisleDiff = parseInt(a.AISLE) - parseInt(b.AISLE);
          if (aisleDiff !== 0) return aisleDiff;
          return parseInt(a.COLUMN) - parseInt(b.COLUMN);
        });
        const firstPick = remaining.shift();
        firstPick.PICK_ORDER = currentOrder;
        orderedPicks.push(firstPick);
        lastPosition = firstPick.position;
        currentOrder++;
      }

      // Greedy: her seferinde en yakın ürünü seç
      while (remaining.length > 0) {
        let minDist = Infinity;
        let nearestIdx = 0;

        for (let i = 0; i < remaining.length; i++) {
          const dist = manhattanDistanceWithCrossAisles(lastPosition, remaining[i].position);
          if (dist < minDist) {
            minDist = dist;
            nearestIdx = i;
          }
        }

        const nearestPick = remaining.splice(nearestIdx, 1)[0];
        nearestPick.PICK_ORDER = currentOrder;
        orderedPicks.push(nearestPick);
        lastPosition = nearestPick.position;
        currentOrder++;
      }
    }
  }

  // TIME bilgisi olmayan ürünleri en sona ekle
  if (picksWithoutTime.length > 0) {
    let remaining = [...picksWithoutTime];
    
    while (remaining.length > 0) {
      if (lastPosition === null) {
        remaining.sort((a, b) => {
          const aisleDiff = parseInt(a.AISLE) - parseInt(b.AISLE);
          if (aisleDiff !== 0) return aisleDiff;
          return parseInt(a.COLUMN) - parseInt(b.COLUMN);
        });
        const firstPick = remaining.shift();
        firstPick.PICK_ORDER = currentOrder;
        orderedPicks.push(firstPick);
        lastPosition = firstPick.position;
        currentOrder++;
      } else {
        let minDist = Infinity;
        let nearestIdx = 0;

        for (let i = 0; i < remaining.length; i++) {
          const dist = manhattanDistanceWithCrossAisles(lastPosition, remaining[i].position);
          if (dist < minDist) {
            minDist = dist;
            nearestIdx = i;
          }
        }

        const nearestPick = remaining.splice(nearestIdx, 1)[0];
        nearestPick.PICK_ORDER = currentOrder;
        orderedPicks.push(nearestPick);
        lastPosition = nearestPick.position;
        currentOrder++;
      }
    }
  }

  if (orderedPicks.length === 0) {
    return [];
  }

  // İlk pick'e göre en yakın asansörü belirle
  const firstPick = orderedPicks[0];
  const firstAisle = parseInt(firstPick.AISLE);
  const nearestElevatorForStart = getNearestElevator(firstAisle);
  const startElevatorAisle = nearestElevatorForStart === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
  
  // Başlangıç asansörüne en yakın merdiveni bul
  const startStairId = getNearestStairToElevator(nearestElevatorForStart);
  const stairToElevatorDist = getStairToElevatorDistance(startStairId, nearestElevatorForStart);

  // === ADIM 0: Merdivende başlangıç ===
  const stairStartRow = {
    'PICKER_CODE': firstPick.PICKER_CODE,
    'PICKCAR_THM': firstPick.PICKCAR_THM,
    'DATE': firstPick.DATE,
    'TIME': '-',
    'AREA': firstPick.AREA,
    'AISLE': '-',
    'COLUMN': '0',
    'SHELF': '-',
    'LEFT_OR_RIGHT': '-',
    'PICKED_THM': '-',
    'ARTICLE_CODE': 'START_AT_STAIR',
    'PICKED_AMOUNT': '0',
    'PICK_ORDER': 0,
    'STEP_DIST': 0,
    'TOTAL_DIST': 0,
    'IS_STAIR_START': true,
    'STAIR_NUM': startStairId,
    'ELEVATOR_NUM': nearestElevatorForStart
  };

  // === ADIM 1: Asansöre varış ===
  const elevatorStartRow = {
    'PICKER_CODE': firstPick.PICKER_CODE,
    'PICKCAR_THM': firstPick.PICKCAR_THM,
    'DATE': firstPick.DATE,
    'TIME': '-',
    'AREA': firstPick.AREA,
    'AISLE': String(startElevatorAisle),
    'COLUMN': '0',
    'SHELF': '-',
    'LEFT_OR_RIGHT': '-',
    'PICKED_THM': '-',
    'ARTICLE_CODE': 'START_AT_ELEVATOR',
    'PICKED_AMOUNT': '0',
    'PICK_ORDER': 1,
    'STEP_DIST': Math.round(stairToElevatorDist * 100) / 100,
    'TOTAL_DIST': Math.round(stairToElevatorDist * 100) / 100,
    'IS_START': true,
    'ELEVATOR_NUM': nearestElevatorForStart
  };

  // STEP_DIST ve TOTAL_DIST hesapla (merdiven + asansör mesafesi eklenerek)
  let totalDistance = stairToElevatorDist;
  let prevPick = null;
  
  for (const pick of orderedPicks) {
    const stepDist = calculateStepDistance(prevPick, pick);
    totalDistance += stepDist;
    pick.STEP_DIST = Math.round(stepDist * 100) / 100;
    pick.TOTAL_DIST = Math.round(totalDistance * 100) / 100;
    prevPick = pick;
  }

  // Son pick bilgileri
  const lastPick = orderedPicks[orderedPicks.length - 1];
  const lastAisle = parseInt(lastPick.AISLE);
  const lastColumn = parseInt(lastPick.COLUMN);
  
  // En yakın asansörü bul (bitiş için)
  const nearestElevatorForEnd = getNearestElevator(lastAisle);
  const endElevatorAisle = nearestElevatorForEnd === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
  
  // Asansöre dönüş mesafesi
  const returnDist = getElevatorToPickDistance(endElevatorAisle, lastAisle, lastColumn);
  totalDistance += returnDist;
  
  // === ADIM N+2: Asansöre dönüş ===
  const elevatorReturnRow = {
    'PICKER_CODE': lastPick.PICKER_CODE,
    'PICKCAR_THM': lastPick.PICKCAR_THM,
    'DATE': lastPick.DATE,
    'TIME': '-',
    'AREA': lastPick.AREA,
    'AISLE': String(endElevatorAisle),
    'COLUMN': '0',
    'SHELF': '-',
    'LEFT_OR_RIGHT': '-',
    'PICKED_THM': '-',
    'ARTICLE_CODE': 'RETURN_TO_ELEVATOR',
    'PICKED_AMOUNT': '0',
    'PICK_ORDER': orderedPicks.length + 2,
    'STEP_DIST': Math.round(returnDist * 100) / 100,
    'TOTAL_DIST': Math.round(totalDistance * 100) / 100,
    'IS_RETURN': true,
    'ELEVATOR_NUM': nearestElevatorForEnd
  };

  // Bitiş asansörüne en yakın merdiveni bul
  const endStairId = getNearestStairToElevator(nearestElevatorForEnd);
  const elevatorToStairDist = getStairToElevatorDistance(endStairId, nearestElevatorForEnd);
  totalDistance += elevatorToStairDist;

  // === ADIM N+3: Merdivene dönüş ===
  const stairReturnRow = {
    'PICKER_CODE': lastPick.PICKER_CODE,
    'PICKCAR_THM': lastPick.PICKCAR_THM,
    'DATE': lastPick.DATE,
    'TIME': '-',
    'AREA': lastPick.AREA,
    'AISLE': '-',
    'COLUMN': '0',
    'SHELF': '-',
    'LEFT_OR_RIGHT': '-',
    'PICKED_THM': '-',
    'ARTICLE_CODE': 'RETURN_TO_STAIR',
    'PICKED_AMOUNT': '0',
    'PICK_ORDER': orderedPicks.length + 3,
    'STEP_DIST': Math.round(elevatorToStairDist * 100) / 100,
    'TOTAL_DIST': Math.round(totalDistance * 100) / 100,
    'IS_STAIR_RETURN': true,
    'STAIR_NUM': endStairId,
    'ELEVATOR_NUM': nearestElevatorForEnd
  };

  // PICK_ORDER'ları 2'den başlayacak şekilde güncelle (0=merdiven, 1=asansör)
  for (let i = 0; i < orderedPicks.length; i++) {
    orderedPicks[i].PICK_ORDER = i + 2;
  }

  // Merdiven başlangıç + Asansör başlangıç + pickler + Asansör bitiş + Merdiven bitiş
  return [stairStartRow, elevatorStartRow, ...orderedPicks, elevatorReturnRow, stairReturnRow];
}

/**
 * Excel verilerini tam olarak işler
 * @param {Array} rawData - Ham Excel verileri
 * @param {Function} onProgress - İlerleme callback'i
 * @returns {Object} İşlenmiş veriler ve istatistikler
 */
export function processExcel(rawData, onProgress = () => {}) {
  onProgress({ stage: 'transform', progress: 0 });

  // 1. Adım: Satırları dönüştür
  const transformedRows = rawData.map((row, index) => {
    if (index % 1000 === 0) {
      onProgress({ stage: 'transform', progress: (index / rawData.length) * 100 });
    }
    return transformRow(row);
  });

  // 1.5. Adım: PICKED_AMOUNT'a göre satırları çoğalt
  // Her birim ayrı bir pick step'i olarak işlenir
  const expandedRows = [];
  for (const row of transformedRows) {
    const amount = parseInt(row.PICKED_AMOUNT) || 1;
    for (let i = 0; i < amount; i++) {
      expandedRows.push({ ...row, PICKED_AMOUNT: '1' });
    }
  }

  onProgress({ stage: 'filter', progress: 0 });

  // 2. Adım: MZN1-6 arealarını filtrele
  const mznRows = expandedRows.filter(row => VALID_AREAS.has(row.AREA));

  onProgress({ stage: 'group', progress: 0 });

  // 3. Adım: PICKER_CODE ve PICKCAR_THM'e göre grupla
  const pickGroups = new Map();
  for (const row of mznRows) {
    const key = `${row.PICKER_CODE}|${row.PICKCAR_THM}`;
    if (!pickGroups.has(key)) {
      pickGroups.set(key, []);
    }
    pickGroups.get(key).push(row);
  }

  onProgress({ stage: 'order', progress: 0 });

  // 4. Adım: Her grup için PICK_ORDER ve mesafe hesapla
  const processedRows = [];
  let groupIndex = 0;
  const totalGroups = pickGroups.size;

  for (const [key, picks] of pickGroups) {
    const orderedPicks = determinePickOrder(picks);
    processedRows.push(...orderedPicks);
    
    groupIndex++;
    if (groupIndex % 10 === 0) {
      onProgress({ stage: 'order', progress: (groupIndex / totalGroups) * 100 });
    }
  }

  // 5. Adım: Sırala
  processedRows.sort((a, b) => {
    const pickerA = String(a.PICKER_CODE || '');
    const pickerB = String(b.PICKER_CODE || '');
    if (pickerA !== pickerB) return pickerA.localeCompare(pickerB);
    
    const pickcarA = String(a.PICKCAR_THM || '');
    const pickcarB = String(b.PICKCAR_THM || '');
    if (pickcarA !== pickcarB) return pickcarA.localeCompare(pickcarB);
    
    const dateA = String(a.DATE || '');
    const dateB = String(b.DATE || '');
    if (dateA !== dateB) return dateA.localeCompare(dateB);
    
    const timeA = String(a.TIME || '99:99');
    const timeB = String(b.TIME || '99:99');
    if (timeA !== timeB) return timeA.localeCompare(timeB);
    
    return (a.PICK_ORDER || 9999) - (b.PICK_ORDER || 9999);
  });

  // Geçici alanları temizle
  for (const row of processedRows) {
    delete row.position;
    delete row.timeMinutes;
  }

  // İstatistikler
  const totalDistance = processedRows.reduce((sum, row) => sum + (row.STEP_DIST || 0), 0);
  const stats = {
    totalRows: rawData.length,
    mznRows: mznRows.length,
    totalGroups: pickGroups.size,
    processedRows: processedRows.length,
    totalDistance: Math.round(totalDistance * 100) / 100
  };

  onProgress({ stage: 'complete', progress: 100 });

  return { data: processedRows, stats };
}

/**
 * İşlenmiş verileri CSV formatına çevirir
 * @param {Array} data - İşlenmiş veriler
 * @returns {string} CSV string
 */
export function toCSV(data) {
  if (!data || data.length === 0) {
    return '';
  }

  const headers = [
    'PICKER_CODE', 'PICKCAR_THM', 'DATE', 'TIME', 'AREA', 'AISLE',
    'COLUMN', 'SHELF', 'LEFT_OR_RIGHT', 'PICKED_THM', 'ARTICLE_CODE',
    'PICKED_AMOUNT', 'PICK_ORDER', 'STEP_DIST', 'TOTAL_DIST'
  ];

  const rows = data.map(row => 
    headers.map(h => row[h] !== undefined ? row[h] : '').join(';')
  );

  return [headers.join(';'), ...rows].join('\n');
}

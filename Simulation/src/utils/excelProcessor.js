import {
  VALID_AREAS,
  getPosition,
  manhattanDistanceWithCrossAisles,
  ELEVATOR_1_AISLE,
  ELEVATOR_2_AISLE,
  getNearestElevator,
  getElevatorToPickDistance,
  getNearestStairToElevator,
  getStairToElevatorDistance
} from './layoutConstants.js';

export const PICK_DATA_FORMATS = {
  LEGACY_EXCEL: 'legacy_excel',
  SOLVER_OUTPUT: 'solver_output'
};

const LEGACY_REQUIRED_COLUMNS = [
  'Kullanıcı Kodu',
  'TOPLANAN_THM',
  'ARTICLE_CODE',
  'DATE_START_EXECUTION',
  'AREA',
  'AISLE',
  'X',
  'Y',
  'Z',
  'TOPLANAN_ADET',
  'PICKCAR_THM'
];

const SOLVER_REQUIRED_COLUMNS = [
  'PICKER_ID',
  'THM_ID',
  'ARTICLE_CODE',
  'FLOOR',
  'AISLE',
  'COLUMN',
  'SHELF',
  'LEFT_OR_RIGHT',
  'AMOUNT',
  'PICKCAR_ID'
];

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

export function inspectPickData(rawData) {
  const normalizedRows = (rawData || [])
    .map(normalizeRawRow)
    .filter((row) => !isRowEmpty(row));

  const firstRow = normalizedRows[0] || {};

  if (Object.keys(firstRow).length === 0) {
    return {
      format: null,
      rows: [],
      missingColumns: LEGACY_REQUIRED_COLUMNS
    };
  }

  const missingLegacyColumns = LEGACY_REQUIRED_COLUMNS.filter((col) => !(col in firstRow));
  if (missingLegacyColumns.length === 0) {
    return {
      format: PICK_DATA_FORMATS.LEGACY_EXCEL,
      rows: normalizedRows,
      missingColumns: []
    };
  }

  const missingSolverColumns = SOLVER_REQUIRED_COLUMNS.filter((col) => !(col in firstRow));
  if (missingSolverColumns.length === 0) {
    return {
      format: PICK_DATA_FORMATS.SOLVER_OUTPUT,
      rows: normalizedRows,
      missingColumns: []
    };
  }

  const legacyMatchCount = LEGACY_REQUIRED_COLUMNS.length - missingLegacyColumns.length;
  const solverMatchCount = SOLVER_REQUIRED_COLUMNS.length - missingSolverColumns.length;

  return {
    format: null,
    rows: normalizedRows,
    missingColumns: legacyMatchCount >= solverMatchCount ? missingLegacyColumns : missingSolverColumns
  };
}

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
  const formats = [
    /^(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)$/i,
    /^(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})(AM|PM)$/i,
    /^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)$/i,
    /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/,
    /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/
  ];

  for (const regex of formats) {
    const match = str.match(regex);
    if (!match) continue;

    const month = match[1].padStart(2, '0');
    const day = match[2].padStart(2, '0');
    const year = match[3];
    const dateTurkish = `${day}.${month}.${year}`;

    if (match.length >= 7) {
      let hours = parseInt(match[4], 10);
      const minutes = match[5];
      const ampm = match[6].toUpperCase();

      if (ampm === 'PM' && hours !== 12) {
        hours += 12;
      } else if (ampm === 'AM' && hours === 12) {
        hours = 0;
      }

      return {
        date: dateTurkish,
        time: `${hours.toString().padStart(2, '0')}:${minutes}`
      };
    }

    return { date: dateTurkish, time: '' };
  }

  console.warn(`Tarih dönüştürme hatası: ${dateStr}`);
  return { date: dateStr, time: '' };
}

function toStringValue(value) {
  return value !== undefined && value !== null ? String(value) : '';
}

/**
 * Eski Excel satırını uygulamanın iç formatına dönüştürür.
 * @param {Object} row - Orijinal Excel satırı
 * @returns {Object} Dönüştürülmüş satır
 */
export function transformRow(row) {
  const { date, time } = transformDateTime(row['DATE_START_EXECUTION']);

  return {
    'PICKER_CODE': toStringValue(row['Kullanıcı Kodu']),
    'PICKCAR_THM': toStringValue(row['PICKCAR_THM']),
    'DATE': date,
    'TIME': time,
    'AREA': toStringValue(row['AREA']),
    'AISLE': toStringValue(row['AISLE']),
    'COLUMN': toStringValue(row['X']),
    'SHELF': toStringValue(row['Y']),
    'LEFT_OR_RIGHT': toStringValue(row['Z']),
    'PICKED_THM': toStringValue(row['TOPLANAN_THM']),
    'ARTICLE_CODE': toStringValue(row['ARTICLE_CODE']),
    'PICKED_AMOUNT': toStringValue(row['TOPLANAN_ADET'])
  };
}

function transformSolverRow(row, index) {
  const pickOrder = parseInt(row['PICK_ORDER'], 10);

  return {
    'PICKER_CODE': toStringValue(row['PICKER_ID']),
    'PICKCAR_THM': toStringValue(row['PICKCAR_ID']),
    'DATE': '',
    'TIME': '',
    'AREA': toStringValue(row['FLOOR']),
    'AISLE': toStringValue(row['AISLE']),
    'COLUMN': toStringValue(row['COLUMN']),
    'SHELF': toStringValue(row['SHELF']),
    'LEFT_OR_RIGHT': toStringValue(row['LEFT_OR_RIGHT']),
    'PICKED_THM': toStringValue(row['THM_ID']),
    'ARTICLE_CODE': toStringValue(row['ARTICLE_CODE']),
    'PICKED_AMOUNT': toStringValue(row['AMOUNT']),
    'SOURCE_PICK_ORDER': Number.isNaN(pickOrder) ? null : pickOrder,
    '__SOURCE_INDEX': index
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
  if (parts.length !== 2) {
    return null;
  }

  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
}

function compareByLocation(a, b) {
  const aisleDiff = parseInt(a.AISLE, 10) - parseInt(b.AISLE, 10);
  if (aisleDiff !== 0) return aisleDiff;

  const columnDiff = parseInt(a.COLUMN, 10) - parseInt(b.COLUMN, 10);
  if (columnDiff !== 0) return columnDiff;

  return (a.__SOURCE_INDEX || 0) - (b.__SOURCE_INDEX || 0);
}

function sortPicksByLocation(picks) {
  return [...picks].sort(compareByLocation);
}

/**
 * İki pick arasındaki mesafeyi hesaplar.
 * İlk pick için en yakın asansörden mesafe hesaplanır.
 * @param {Object|null} prevPick - Önceki pick (ilk pick için null)
 * @param {Object} currPick - Mevcut pick
 * @returns {number} Mesafe (metre)
 */
function calculateStepDistance(prevPick, currPick) {
  const currAisle = parseInt(currPick.AISLE, 10);
  const currColumn = parseInt(currPick.COLUMN, 10);

  if (!prevPick) {
    const nearestElevator = getNearestElevator(currAisle);
    const elevatorAisle = nearestElevator === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
    return getElevatorToPickDistance(elevatorAisle, currAisle, currColumn);
  }

  if (
    parseInt(prevPick.AISLE, 10) === currAisle &&
    parseInt(prevPick.COLUMN, 10) === currColumn
  ) {
    return 0;
  }

  return manhattanDistanceWithCrossAisles(prevPick.position, currPick.position);
}

function buildSimulationRows(orderedPicks) {
  if (orderedPicks.length === 0) {
    return [];
  }

  const firstPick = orderedPicks[0];
  const firstAisle = parseInt(firstPick.AISLE, 10);
  const nearestElevatorForStart = getNearestElevator(firstAisle);
  const startElevatorAisle =
    nearestElevatorForStart === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
  const startStairId = getNearestStairToElevator(nearestElevatorForStart);
  const stairToElevatorDist = getStairToElevatorDistance(
    startStairId,
    nearestElevatorForStart
  );

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

  let totalDistance = stairToElevatorDist;
  let prevPick = null;

  for (let i = 0; i < orderedPicks.length; i++) {
    const pick = orderedPicks[i];
    const stepDist = calculateStepDistance(prevPick, pick);
    totalDistance += stepDist;
    pick.STEP_DIST = Math.round(stepDist * 100) / 100;
    pick.TOTAL_DIST = Math.round(totalDistance * 100) / 100;
    pick.PICK_ORDER = i + 2;
    prevPick = pick;
  }

  const lastPick = orderedPicks[orderedPicks.length - 1];
  const lastAisle = parseInt(lastPick.AISLE, 10);
  const lastColumn = parseInt(lastPick.COLUMN, 10);
  const nearestElevatorForEnd = getNearestElevator(lastAisle);
  const endElevatorAisle =
    nearestElevatorForEnd === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
  const returnDist = getElevatorToPickDistance(endElevatorAisle, lastAisle, lastColumn);
  totalDistance += returnDist;

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

  const endStairId = getNearestStairToElevator(nearestElevatorForEnd);
  const elevatorToStairDist = getStairToElevatorDistance(
    endStairId,
    nearestElevatorForEnd
  );
  totalDistance += elevatorToStairDist;

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

  return [stairStartRow, elevatorStartRow, ...orderedPicks, elevatorReturnRow, stairReturnRow];
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

  for (const pick of picks) {
    pick.position = getPosition(parseInt(pick.AISLE, 10), parseInt(pick.COLUMN, 10));
    pick.timeMinutes = parseTime(pick.TIME);
  }

  const hasExplicitOrder = picks.some((pick) => Number.isFinite(pick.SOURCE_PICK_ORDER));
  if (hasExplicitOrder) {
    const orderedPicks = [...picks].sort((a, b) => {
      const orderA = a.SOURCE_PICK_ORDER ?? Number.MAX_SAFE_INTEGER;
      const orderB = b.SOURCE_PICK_ORDER ?? Number.MAX_SAFE_INTEGER;
      if (orderA !== orderB) return orderA - orderB;

      const locationDiff = compareByLocation(a, b);
      if (locationDiff !== 0) return locationDiff;

      return (a.__SOURCE_INDEX || 0) - (b.__SOURCE_INDEX || 0);
    });

    return buildSimulationRows(orderedPicks);
  }

  const picksWithTime = picks.filter((pick) => pick.timeMinutes !== null);
  const picksWithoutTime = picks.filter((pick) => pick.timeMinutes === null);

  if (picksWithTime.length === 0) {
    return buildSimulationRows(sortPicksByLocation(picks));
  }

  const timeGroups = new Map();
  for (const pick of picksWithTime) {
    const key = pick.timeMinutes;
    if (!timeGroups.has(key)) {
      timeGroups.set(key, []);
    }
    timeGroups.get(key).push(pick);
  }

  const sortedTimes = [...timeGroups.keys()].sort((a, b) => a - b);
  const orderedPicks = [];
  let lastPosition = null;

  for (const timeMinute of sortedTimes) {
    let remaining = [...timeGroups.get(timeMinute)];

    if (remaining.length === 1) {
      orderedPicks.push(remaining[0]);
      lastPosition = remaining[0].position;
      continue;
    }

    if (lastPosition === null) {
      remaining = sortPicksByLocation(remaining);
      const firstPick = remaining.shift();
      orderedPicks.push(firstPick);
      lastPosition = firstPick.position;
    }

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
      orderedPicks.push(nearestPick);
      lastPosition = nearestPick.position;
    }
  }

  if (picksWithoutTime.length > 0) {
    let remaining = [...picksWithoutTime];

    while (remaining.length > 0) {
      if (lastPosition === null) {
        remaining = sortPicksByLocation(remaining);
        const firstPick = remaining.shift();
        orderedPicks.push(firstPick);
        lastPosition = firstPick.position;
        continue;
      }

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
      orderedPicks.push(nearestPick);
      lastPosition = nearestPick.position;
    }
  }

  return buildSimulationRows(orderedPicks);
}

/**
 * Pick verilerini işler
 * @param {Array} rawData - Ham satırlar
 * @param {Function} onProgress - İlerleme callback'i
 * @returns {Object} İşlenmiş veriler ve istatistikler
 */
export function processExcel(rawData, onProgress = () => {}) {
  const inspection = inspectPickData(rawData);
  if (!inspection.format) {
    throw new Error(`Eksik kolonlar: ${inspection.missingColumns.join(', ')}`);
  }

  const normalizedRows = inspection.rows;
  onProgress({ stage: 'transform', progress: 0 });

  const transformedRows = normalizedRows.map((row, index) => {
    if (index % 1000 === 0) {
      onProgress({
        stage: 'transform',
        progress: (index / Math.max(normalizedRows.length, 1)) * 100
      });
    }

    return inspection.format === PICK_DATA_FORMATS.SOLVER_OUTPUT
      ? transformSolverRow(row, index)
      : transformRow(row);
  });

  const expandedRows =
    inspection.format === PICK_DATA_FORMATS.SOLVER_OUTPUT
      ? transformedRows
      : transformedRows.flatMap((row) => {
          const amount = parseInt(row.PICKED_AMOUNT, 10) || 1;
          return Array.from({ length: amount }, () => ({ ...row, PICKED_AMOUNT: '1' }));
        });

  onProgress({ stage: 'filter', progress: 0 });

  const mznRows = expandedRows.filter((row) => VALID_AREAS.has(row.AREA));

  onProgress({ stage: 'group', progress: 0 });

  const pickGroups = new Map();
  for (const row of mznRows) {
    const key = `${row.PICKER_CODE}|${row.PICKCAR_THM}`;
    if (!pickGroups.has(key)) {
      pickGroups.set(key, []);
    }
    pickGroups.get(key).push(row);
  }

  onProgress({ stage: 'order', progress: 0 });

  const processedRows = [];
  let groupIndex = 0;
  const totalGroups = Math.max(pickGroups.size, 1);

  for (const [, picks] of pickGroups) {
    processedRows.push(...determinePickOrder(picks));
    groupIndex++;

    if (groupIndex % 10 === 0 || groupIndex === pickGroups.size) {
      onProgress({
        stage: 'order',
        progress: (groupIndex / totalGroups) * 100
      });
    }
  }

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

    return (a.PICK_ORDER ?? 9999) - (b.PICK_ORDER ?? 9999);
  });

  for (const row of processedRows) {
    delete row.position;
    delete row.timeMinutes;
    delete row.SOURCE_PICK_ORDER;
    delete row.__SOURCE_INDEX;
  }

  const totalDistance = processedRows.reduce((sum, row) => sum + (row.STEP_DIST || 0), 0);
  const stats = {
    totalRows: normalizedRows.length,
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
    'PICKER_CODE',
    'PICKCAR_THM',
    'DATE',
    'TIME',
    'AREA',
    'AISLE',
    'COLUMN',
    'SHELF',
    'LEFT_OR_RIGHT',
    'PICKED_THM',
    'ARTICLE_CODE',
    'PICKED_AMOUNT',
    'PICK_ORDER',
    'STEP_DIST',
    'TOTAL_DIST'
  ];

  const rows = data.map((row) =>
    headers.map((header) => (row[header] !== undefined ? row[header] : '')).join(';')
  );

  return [headers.join(';'), ...rows].join('\n');
}

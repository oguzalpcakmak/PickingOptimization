const REQUIRED_COLUMNS = [
  'ARTICLE_CODE',
  'THM_ID',
  'FLOOR',
  'AISLE',
  'COLUMN',
  'SHELF',
  'LEFT_OR_RIGHT',
  'IS_SELECTED'
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

function toStringValue(value) {
  return value !== undefined && value !== null ? String(value).trim() : '';
}

function isSelectedValue(value) {
  const normalized = toStringValue(value).toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes';
}

export function inspectAlternativeLocations(rawData) {
  const normalizedRows = (rawData || [])
    .map(normalizeRawRow)
    .filter((row) => !isRowEmpty(row));

  const firstRow = normalizedRows[0] || {};
  const missingColumns = REQUIRED_COLUMNS.filter((column) => !(column in firstRow));

  return {
    valid: missingColumns.length === 0,
    rows: normalizedRows,
    missingColumns
  };
}

export function processAlternativeLocations(rawData) {
  const inspection = inspectAlternativeLocations(rawData);
  if (!inspection.valid) {
    throw new Error(`Eksik kolonlar: ${inspection.missingColumns.join(', ')}`);
  }

  const transformedRows = inspection.rows.map((row) => ({
    ARTICLE_CODE: toStringValue(row['ARTICLE_CODE']),
    THM_ID: toStringValue(row['THM_ID']),
    AREA: toStringValue(row['FLOOR']),
    AISLE: toStringValue(row['AISLE']),
    COLUMN: toStringValue(row['COLUMN']),
    SHELF: toStringValue(row['SHELF']),
    LEFT_OR_RIGHT: toStringValue(row['LEFT_OR_RIGHT']).toUpperCase(),
    IS_SELECTED: isSelectedValue(row['IS_SELECTED'])
  }));

  const alternativeRows = transformedRows.filter((row) => !row.IS_SELECTED);
  const uniqueCells = new Set(
    alternativeRows.map((row) => {
      const visualSide = row.LEFT_OR_RIGHT === 'L' ? 'R' : 'L';
      return `${row.AISLE}|${row.COLUMN}|${visualSide}`;
    })
  );

  return {
    data: alternativeRows,
    stats: {
      totalRows: inspection.rows.length,
      alternativeRows: alternativeRows.length,
      uniqueCells: uniqueCells.size
    }
  };
}

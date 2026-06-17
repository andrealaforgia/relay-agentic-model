#!/usr/bin/env node
// Map a canonical CSV row [date, description, amount] into a ledger entry.
//
// A "ledger entry" is an object exposing three independently-addressable,
// named components:
//   - date:        a real calendar Date (UTC midnight, no timezone drift)
//   - description: the original middle field, verbatim
//   - amount:      a JavaScript number usable in arithmetic
//
// Rows that are not exactly three fields, or whose fields cannot be mapped to
// these meanings, are rejected: instead of returning an entry, these functions
// throw a RowError. A separate tryParseRow() surfaces rejection as a value.

/** Distinct, observable rejection signal — never confused with a valid entry. */
export class RowError extends Error {
  constructor(message) {
    super(message);
    this.name = "RowError";
  }
}

// Strict ISO calendar date: YYYY-MM-DD only (no time, no timezone, no slack).
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

// Optional leading sign, digits, optional single decimal point + digits.
// Accepts "100", "100.0", "100.00", "-42.50", "+100.00".
const DECIMAL = /^[+-]?(\d+(\.\d+)?|\.\d+)$/;

/**
 * Parse the date field into a real calendar Date.
 * Interprets YYYY-MM-DD as a plain calendar day anchored at UTC midnight so the
 * observed year/month/day equal what was written, with no timezone shifting.
 * Rejects impossible dates (e.g. 2026-13-40, 2026-02-30) and non-dates.
 */
function parseDateField(field) {
  if (field === "") throw new RowError("empty date field");
  const m = ISO_DATE.exec(field);
  if (!m) throw new RowError(`unparseable date: ${JSON.stringify(field)}`);
  const year = Number(m[1]);
  const month = Number(m[2]); // 1-12 as written
  const day = Number(m[3]); // 1-31 as written
  // Build at UTC midnight so day/month/year are preserved regardless of host TZ.
  const date = new Date(Date.UTC(year, month - 1, day));
  // Reject roll-over from impossible components (e.g. month 13, day 40, Feb 30).
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    throw new RowError(`impossible calendar date: ${JSON.stringify(field)}`);
  }
  return date;
}

/** Validate the description field — preserved verbatim, only rejecting empty. */
function parseDescriptionField(field) {
  if (field === "") throw new RowError("empty description field");
  return field; // byte-for-byte: no trim, no case-fold, no space-collapse.
}

/** Parse the amount field into a number usable in arithmetic. */
function parseAmountField(field) {
  if (field === "") throw new RowError("empty amount field");
  if (!DECIMAL.test(field)) {
    throw new RowError(`non-numeric amount: ${JSON.stringify(field)}`);
  }
  const amount = Number(field);
  if (!Number.isFinite(amount)) {
    throw new RowError(`non-finite amount: ${JSON.stringify(field)}`);
  }
  return amount;
}

/**
 * Map one canonical row [date, description, amount] into a ledger entry.
 * Throws RowError on any malformed row (wrong field count or unmappable field).
 *
 * @param {string[]} row
 * @returns {{date: Date, description: string, amount: number}}
 */
export function parseRow(row) {
  if (!Array.isArray(row)) {
    throw new RowError("row must be an array of fields");
  }
  if (row.length !== 3) {
    throw new RowError(
      `expected exactly 3 fields [date, description, amount], got ${row.length}`,
    );
  }
  const [dateField, descriptionField, amountField] = row;
  // Each field is validated by position; nothing is borrowed or shifted.
  const date = parseDateField(dateField);
  const description = parseDescriptionField(descriptionField);
  const amount = parseAmountField(amountField);
  return { date, description, amount };
}

/**
 * Non-throwing variant: returns a tagged result so rejection is a value.
 * @param {string[]} row
 * @returns {{ok: true, entry: object} | {ok: false, error: string}}
 */
export function tryParseRow(row) {
  try {
    return { ok: true, entry: parseRow(row) };
  } catch (err) {
    if (err instanceof RowError) return { ok: false, error: err.message };
    throw err;
  }
}

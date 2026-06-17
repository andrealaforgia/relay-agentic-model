#!/usr/bin/env node
// Derive the calendar month (year, month-of-year) of a transaction.
//
// A "calendar month" is the (year, month-of-year) pair a transaction's date
// falls in — no finer (the day is discarded) and no coarser (the year alone is
// not enough). Two calendar months are equal exactly when their year AND their
// month-of-year coincide; same month-number in different years are distinct,
// and any two days within one month yield one identical calendar month.
//
// The derivation is a pure function of the transaction's own UTC date: the same
// date always yields the same calendar month, regardless of when, how often, or
// in what order it is processed.

// Month names indexed by month-of-year (1 = January … 12 = December).
const MONTH_NAMES = [
  null,
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/**
 * A value object for a (year, month-of-year) pair.
 * Immutable; equality is by value over (year, month) only.
 */
export class CalendarMonth {
  /**
   * @param {number} year      full calendar year (e.g. 2023)
   * @param {number} month     month-of-year, 1 (January) … 12 (December)
   */
  constructor(year, month) {
    if (!Number.isInteger(year)) {
      throw new TypeError(`year must be an integer, got ${year}`);
    }
    if (!Number.isInteger(month) || month < 1 || month > 12) {
      throw new RangeError(`month must be 1-12, got ${month}`);
    }
    this.year = year;
    this.month = month; // month-of-year, 1-based
    Object.freeze(this);
  }

  /** The English month name, e.g. "March". */
  get name() {
    return MONTH_NAMES[this.month];
  }

  /** Value equality: same year AND same month-of-year. */
  equals(other) {
    return (
      other instanceof CalendarMonth &&
      this.year === other.year &&
      this.month === other.month
    );
  }

  /**
   * A canonical, collision-free key for grouping/comparison: "YYYY-MM".
   * Two calendar months share a key exactly when they are equal.
   */
  key() {
    return `${String(this.year).padStart(4, "0")}-${String(this.month).padStart(2, "0")}`;
  }

  /** Human-readable form, e.g. "(2023, March)". */
  toString() {
    return `(${this.year}, ${this.name})`;
  }
}

/**
 * Derive the calendar month of a transaction from its date.
 *
 * Reads only the transaction's own date — specifically its UTC year and
 * month-of-year — and discards the day-of-month and everything finer. The
 * date is read in UTC to match how transaction dates are anchored (UTC
 * midnight in ledger_entry.mjs), so no host timezone can shift the result.
 *
 * @param {{date: Date}} transaction  an object exposing a `date` Date
 * @returns {CalendarMonth} the (year, month-of-year) the date falls in
 */
export function calendarMonthOf(transaction) {
  if (transaction == null || !(transaction.date instanceof Date)) {
    throw new TypeError("transaction must expose a `date` of type Date");
  }
  const date = transaction.date;
  if (Number.isNaN(date.getTime())) {
    throw new RangeError("transaction date is not a valid calendar date");
  }
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth() + 1; // getUTCMonth is 0-based; make it 1-based
  return new CalendarMonth(year, month);
}

#!/usr/bin/env node
// Aggregate signed ledger amounts into per-calendar-month totals.
//
// A "month total" is the arithmetic sum of the signed amounts of every record
// carrying that calendar month. Positive amounts raise the total, negative
// amounts lower it; the net is exact even when they mix or cancel. The set of
// months in the output is exactly the set of distinct calendar months present
// in the input — none invented, none dropped — where months are distinguished
// by (year, month-of-year), so the same calendar month in different years is
// two distinct months (see calendar_month.mjs).
//
// A zero-amount record is, by sign, neither income nor expense: the income
// boundary is strictly > 0 and the expense boundary is strictly < 0, so 0
// belongs to neither classification. It still attributes its month to the
// output (the month appears) and contributes exactly 0 to that month's total.

import { CalendarMonth, calendarMonthOf } from "./calendar_month.mjs";

/**
 * Sign-based classification of a single amount.
 * Income is strictly positive; expense is strictly negative; zero is neither.
 * @param {number} amount
 * @returns {"income" | "expense" | "neither"}
 */
export function classify(amount) {
  if (!Number.isFinite(amount)) {
    throw new TypeError(`amount must be a finite number, got ${amount}`);
  }
  if (amount > 0) return "income";
  if (amount < 0) return "expense";
  return "neither"; // exactly zero — neither income nor expense
}

/**
 * Immutable view of one month's computed total.
 * Carries the CalendarMonth it belongs to and the summed signed amount.
 */
export class MonthTotal {
  /**
   * @param {CalendarMonth} month
   * @param {number} total  the summed signed amount for this month
   */
  constructor(month, total) {
    if (!(month instanceof CalendarMonth)) {
      throw new TypeError("month must be a CalendarMonth");
    }
    if (!Number.isFinite(total)) {
      throw new TypeError(`total must be a finite number, got ${total}`);
    }
    this.month = month;
    this.total = total;
    Object.freeze(this);
  }
}

/**
 * Compute per-month totals from a collection of records.
 *
 * Each record must expose a signed `amount` and a way to derive its calendar
 * month — either a `date` Date (via calendarMonthOf) or a `month`/`calendarMonth`
 * that is already a CalendarMonth.
 *
 * Properties guaranteed (the outstanding expectations):
 *  - Empty input → empty result: zero months.
 *  - A month's total is the arithmetic sum of its records' signed amounts.
 *  - Months are keyed by (year, month-of-year); same month, different year is
 *    distinct.
 *  - The output's month set equals the input's distinct-month set exactly.
 *  - A zero-amount record still attributes its month (it appears) and adds 0.
 *  - Each month's total depends only on records carrying that month, so adding
 *    or removing one record shifts only its own month by exactly its amount.
 *
 * @param {Iterable<{amount: number, date?: Date, month?: CalendarMonth, calendarMonth?: CalendarMonth}>} records
 * @returns {Map<string, MonthTotal>} keyed by CalendarMonth.key() ("YYYY-MM")
 */
export function monthTotals(records) {
  const totals = new Map(); // key -> { month, sum }
  if (records == null) return new Map();
  for (const record of records) {
    if (record == null || !Number.isFinite(record.amount)) {
      throw new TypeError("each record must expose a finite `amount`");
    }
    const month = monthOf(record);
    const key = month.key();
    const existing = totals.get(key);
    if (existing === undefined) {
      // First record for this month: the month now appears, even at amount 0.
      totals.set(key, { month, sum: record.amount });
    } else {
      // Accumulate: positive raises, negative lowers, zero is a no-op net change.
      existing.sum += record.amount;
    }
  }
  // Freeze each entry into an immutable MonthTotal value.
  const out = new Map();
  for (const [key, { month, sum }] of totals) {
    out.set(key, new MonthTotal(month, sum));
  }
  return out;
}

/** Derive the CalendarMonth of a record from whichever field it carries. */
function monthOf(record) {
  if (record.calendarMonth instanceof CalendarMonth) return record.calendarMonth;
  if (record.month instanceof CalendarMonth) return record.month;
  if (record.date instanceof Date) return calendarMonthOf(record);
  throw new TypeError(
    "each record must expose a `date` Date or a `month`/`calendarMonth` CalendarMonth",
  );
}

/**
 * Convenience: read back one month's total as a plain number.
 * Returns undefined when that month is absent from the totals.
 * @param {Map<string, MonthTotal>} totals  output of monthTotals()
 * @param {CalendarMonth} month
 * @returns {number | undefined}
 */
export function totalFor(totals, month) {
  if (!(month instanceof CalendarMonth)) {
    throw new TypeError("month must be a CalendarMonth");
  }
  const entry = totals.get(month.key());
  return entry === undefined ? undefined : entry.total;
}

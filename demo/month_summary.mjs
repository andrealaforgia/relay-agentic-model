#!/usr/bin/env node
// Render a per-calendar-month summary from income/expense entries.
//
// The summary is a list of LINES, one per distinct calendar month present in
// the input. Each line names its month and surfaces three figures for that
// month:
//   - income:  Σ of that month's income magnitudes   (>= 0)
//   - expense: Σ of that month's expense magnitudes   (>= 0)
//   - net:     income − expense                       (signed)
//
// The figures live in the same model as month_net.mjs: an entry carries a
// `kind` ("income" | "expense") and a non-negative `amount` magnitude — the
// sign is in the kind, not the number. A month is the (year, month-of-year)
// pair from calendar_month.mjs, so the same month-of-year in two different
// years is two distinct lines, and two entries in the very same month share
// one line.
//
// Properties guaranteed (the outstanding expectations):
//  - E1 One line per distinct month present; no duplicates, no invented months.
//  - E2 Lines in strict chronological order (year, then month-of-year).
//  - E3 Each line carries month + income + expense + net; a side with no entries
//       shows 0; income and expense are non-negative magnitudes.
//  - E4 net === income − expense on every line (positive / negative / zero).
//  - E5 Each line is computed solely from entries of its own month.
//  - E6 No entries → no lines (empty summary; no placeholder, no zero line).

import { CalendarMonth, calendarMonthOf } from "./calendar_month.mjs";
import { INCOME, EXPENSE } from "./month_net.mjs";

/**
 * Immutable summary line for a single calendar month.
 * Net is derived from income and expense at construction so the three figures
 * are always mutually consistent (net === income − expense).
 */
export class MonthSummaryLine {
  /**
   * @param {CalendarMonth} month
   * @param {number} income   sum of this month's income magnitudes (>= 0)
   * @param {number} expense  sum of this month's expense magnitudes (>= 0)
   */
  constructor(month, income, expense) {
    if (!(month instanceof CalendarMonth)) {
      throw new TypeError("month must be a CalendarMonth");
    }
    if (!Number.isFinite(income) || income < 0) {
      throw new RangeError(`income must be a non-negative magnitude, got ${income}`);
    }
    if (!Number.isFinite(expense) || expense < 0) {
      throw new RangeError(`expense must be a non-negative magnitude, got ${expense}`);
    }
    this.month = month;
    this.income = income;
    this.expense = expense;
    this.net = income - expense; // E4: derived, never stored independently
    Object.freeze(this);
  }

  /** A single rendered text line, e.g. "2023-03  income 1500  expense 400  net 1100". */
  render() {
    return (
      `${this.month.key()}  ` +
      `income ${this.income}  ` +
      `expense ${this.expense}  ` +
      `net ${this.net}`
    );
  }
}

/** Derive the CalendarMonth an entry belongs to from whichever field it carries. */
function monthOf(entry) {
  if (entry.calendarMonth instanceof CalendarMonth) return entry.calendarMonth;
  if (entry.month instanceof CalendarMonth) return entry.month;
  if (entry.date instanceof Date) return calendarMonthOf(entry);
  throw new TypeError(
    "each entry must expose a `date` Date or a `month`/`calendarMonth` CalendarMonth",
  );
}

/** Validate one entry's amount as a non-negative magnitude. */
function magnitudeOf(entry) {
  const amount = entry.amount;
  if (!Number.isFinite(amount)) {
    throw new TypeError(`amount must be a finite number, got ${amount}`);
  }
  if (amount < 0) {
    throw new RangeError(`amount must be a non-negative magnitude, got ${amount}`);
  }
  return amount;
}

/**
 * Build the per-month summary lines from a collection of entries.
 *
 * Each entry exposes:
 *   - kind:   "income" | "expense"
 *   - amount: a non-negative magnitude
 *   - a calendar month, via `calendarMonth`/`month` (a CalendarMonth) or `date`.
 *
 * Returns an array of MonthSummaryLine in strict chronological order. The set
 * of months equals exactly the distinct months present in the input (E1);
 * empty input yields an empty array (E6). Each line aggregates only entries of
 * its own month (E5), with absent sides defaulting to 0 (E3).
 *
 * @param {Iterable<{kind: string, amount: number, date?: Date, month?: CalendarMonth, calendarMonth?: CalendarMonth}>} entries
 * @returns {MonthSummaryLine[]} chronologically ordered, one per distinct month
 */
export function monthSummary(entries) {
  // key -> { month, income, expense } accumulator, only for months that appear.
  const acc = new Map();
  if (entries == null) return []; // E6: nothing in → nothing out
  for (const entry of entries) {
    if (entry == null) {
      throw new TypeError("each entry must be a non-null object");
    }
    const month = monthOf(entry);
    const amount = magnitudeOf(entry);
    const key = month.key();
    let bucket = acc.get(key);
    if (bucket === undefined) {
      // First entry for this month: the month now appears, both sides start at 0.
      bucket = { month, income: 0, expense: 0 };
      acc.set(key, bucket);
    }
    // E5: an entry only ever touches its own month's bucket.
    if (entry.kind === INCOME) {
      bucket.income += amount;
    } else if (entry.kind === EXPENSE) {
      bucket.expense += amount;
    } else {
      throw new TypeError(
        `kind must be "income" or "expense", got ${JSON.stringify(entry.kind)}`,
      );
    }
  }

  // E2: sort by the canonical "YYYY-MM" key — lexicographic order over a
  // zero-padded year-then-month string is identical to chronological order.
  const lines = [];
  for (const { month, income, expense } of acc.values()) {
    lines.push(new MonthSummaryLine(month, income, expense));
  }
  lines.sort((a, b) => a.month.key().localeCompare(b.month.key()));
  return lines;
}

/**
 * Render the whole summary as text: one line per month, newline-joined,
 * in chronological order. Empty input renders the empty string (no lines).
 *
 * @param {Iterable} entries  same shape as monthSummary()
 * @returns {string}
 */
export function renderMonthSummary(entries) {
  return monthSummary(entries).map((line) => line.render()).join("\n");
}

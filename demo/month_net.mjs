#!/usr/bin/env node
// Compute a calendar month's NET from its income and expense entries.
//
// An "entry" carries a kind and a non-negative magnitude:
//   - kind "income"  → an amount the month received
//   - kind "expense" → an amount the month paid out
// The NET of a month is, by definition, the sum of that month's income
// amounts minus the sum of that month's expense amounts:
//
//     net(month) = Σ income(month) − Σ expense(month)
//
// Consequences that fall directly out of that single definition:
//   - Income with no expenses → net equals the income total (absent expenses
//     contribute exactly 0).
//   - Expenses with no income → net is the negated expense total (negative).
//   - No entries at all → empty sums on both sides → net is 0.
//   - Expenses exceeding income → net is negative, exactly income − expense.
//   - Each month sums only its own entries; one month never bleeds into another.
//   - Summation is commutative, so the order entries are presented in is
//     irrelevant to the net.
//
// This is the income/expense-typed sibling of month_totals.mjs (which sums a
// single pre-signed amount). Here the sign is supplied by the entry's kind, not
// baked into the amount, so amounts are magnitudes (>= 0).

import { CalendarMonth, calendarMonthOf } from "./calendar_month.mjs";

/** The two recognised entry kinds. */
export const INCOME = "income";
export const EXPENSE = "expense";

/**
 * Turn one entry's (kind, amount) into the signed contribution it makes to its
 * month's net: income adds, expense subtracts.
 * @param {"income"|"expense"} kind
 * @param {number} amount  a non-negative magnitude
 * @returns {number} +amount for income, -amount for expense
 */
export function signedContribution(kind, amount) {
  if (!Number.isFinite(amount)) {
    throw new TypeError(`amount must be a finite number, got ${amount}`);
  }
  if (amount < 0) {
    throw new RangeError(`amount must be a non-negative magnitude, got ${amount}`);
  }
  if (kind === INCOME) return amount;
  if (kind === EXPENSE) return -amount;
  throw new TypeError(`kind must be "income" or "expense", got ${JSON.stringify(kind)}`);
}

/**
 * Immutable view of one month's computed net.
 */
export class MonthNet {
  /**
   * @param {CalendarMonth} month
   * @param {number} net  Σ income − Σ expense for this month
   */
  constructor(month, net) {
    if (!(month instanceof CalendarMonth)) {
      throw new TypeError("month must be a CalendarMonth");
    }
    if (!Number.isFinite(net)) {
      throw new TypeError(`net must be a finite number, got ${net}`);
    }
    this.month = month;
    this.net = net;
    Object.freeze(this);
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

/**
 * Compute per-month net from a collection of income/expense entries.
 *
 * Each entry exposes:
 *   - kind:   "income" | "expense"
 *   - amount: a non-negative magnitude
 *   - a calendar month, via `calendarMonth`/`month` (a CalendarMonth) or `date`.
 *
 * @param {Iterable<{kind: string, amount: number, date?: Date, month?: CalendarMonth, calendarMonth?: CalendarMonth}>} entries
 * @returns {Map<string, MonthNet>} keyed by CalendarMonth.key() ("YYYY-MM")
 */
export function monthNets(entries) {
  const acc = new Map(); // key -> { month, net }
  if (entries == null) return new Map();
  for (const entry of entries) {
    if (entry == null) {
      throw new TypeError("each entry must be a non-null object");
    }
    const month = monthOf(entry);
    const delta = signedContribution(entry.kind, entry.amount);
    const key = month.key();
    const existing = acc.get(key);
    if (existing === undefined) {
      acc.set(key, { month, net: delta });
    } else {
      existing.net += delta; // income raises, expense lowers — only this month
    }
  }
  const out = new Map();
  for (const [key, { month, net }] of acc) {
    out.set(key, new MonthNet(month, net));
  }
  return out;
}

/**
 * Net for a single month computed from that month's entries alone.
 * A month with no entries of either kind nets to 0.
 *
 * @param {Iterable<{kind: string, amount: number}>} entries  one month's entries
 * @returns {number} Σ income − Σ expense (0 when there are no entries)
 */
export function netOf(entries) {
  let net = 0;
  if (entries == null) return net;
  for (const entry of entries) {
    if (entry == null) {
      throw new TypeError("each entry must be a non-null object");
    }
    net += signedContribution(entry.kind, entry.amount);
  }
  return net;
}

/**
 * Read back one month's net as a plain number.
 * Returns undefined when that month is absent from the nets.
 * @param {Map<string, MonthNet>} nets  output of monthNets()
 * @param {CalendarMonth} month
 * @returns {number | undefined}
 */
export function netFor(nets, month) {
  if (!(month instanceof CalendarMonth)) {
    throw new TypeError("month must be a CalendarMonth");
  }
  const entry = nets.get(month.key());
  return entry === undefined ? undefined : entry.net;
}

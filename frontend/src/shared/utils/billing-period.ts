import { format, parse, subMonths } from "date-fns";

import { kyivNow } from "./deadline";

/**
 * Period residents currently submit a reading for (the prior calendar month), as
 * YYYY-MM. Follows Kyiv time, matching the backend's `current_billing_period()`,
 * which rejects any other period.
 */
export function currentBillingPeriod(now: Date = kyivNow()): string {
  return format(subMonths(now, 1), "yyyy-MM");
}

/** The billing period after the current one, as YYYY-MM. */
export function nextBillingPeriod(now: Date = kyivNow()): string {
  return format(now, "yyyy-MM");
}

/** First day of a YYYY-MM period, in local time. */
export function periodToDate(period: string): Date {
  return parse(period, "yyyy-MM", new Date(0));
}

/** Localized month name for a YYYY-MM period, e.g. "серпень 2026 р." for uk-UA. */
export function formatPeriodMonth(
  period: string,
  locale: string,
  options: Intl.DateTimeFormatOptions = { month: "long" }
): string {
  return new Intl.DateTimeFormat(locale, options).format(periodToDate(period));
}

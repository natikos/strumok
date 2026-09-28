import { format, subMonths } from "date-fns";

/** Period residents currently submit a reading for (the prior calendar month), as YYYY-MM. */
export function currentBillingPeriod(now: Date = new Date()): string {
  return format(subMonths(now, 1), "yyyy-MM");
}

/** The billing period after the current one, as YYYY-MM. */
export function nextBillingPeriod(now: Date = new Date()): string {
  return format(now, "yyyy-MM");
}

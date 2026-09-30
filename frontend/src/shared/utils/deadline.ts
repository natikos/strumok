import {
  differenceInCalendarDays,
  endOfDay,
  format,
  getMonth,
  isAfter,
  isBefore,
  isWithinInterval,
  setDate,
  startOfDay,
  startOfToday,
  subMonths,
} from "date-fns";

export const DEADLINE_DAY = 5;

export type DeadlineStatus = "due" | "overdue" | "submitted" | "submitted-late";

export interface DeadlineRange {
  start: Date;
  end: Date;
}

export function getSubmitWindow(now: Date = new Date()): DeadlineRange {
  return {
    start: startOfDay(setDate(now, 1)),
    end: endOfDay(setDate(now, DEADLINE_DAY)),
  };
}

/** Month the submit window closes in, not the billing period being reported on. */
export function getDeadlineMonthIndex(now: Date = new Date()): number {
  return getMonth(getSubmitWindow(now).end);
}

/** Billing period (yyyy-MM) that residents are submitting readings for at `now`. */
export function getBillingPeriod(now: Date = new Date()): string {
  return format(subMonths(now, 1), "yyyy-MM");
}

export function getDeadlineStatus(submittedAt: string | null | undefined): DeadlineStatus {
  const window = getSubmitWindow();

  if (isOverdue(submittedAt)) {
    return "overdue";
  }

  if (isPending(submittedAt)) {
    return "due";
  }

  // If the submission is not overdue and not pending, it means it has been submitted.
  return isWithinInterval(submittedAt!, window) ? "submitted" : "submitted-late";
}

export function isOverdue(submittedAt: string | null | undefined): boolean {
  const window = getSubmitWindow();

  if (!submittedAt) {
    return isAfter(new Date(), window.end);
  }

  return isBefore(submittedAt, window.start) && isAfter(new Date(), window.end);
}

export function isPending(submittedAt: string | null | undefined): boolean {
  const window = getSubmitWindow();

  if (!submittedAt) {
    return isWithinInterval(new Date(), window);
  }

  return isBefore(submittedAt, window.start);
}

export function getDaysLeft(): number {
  const { end } = getSubmitWindow();
  return differenceInCalendarDays(end, startOfToday());
}

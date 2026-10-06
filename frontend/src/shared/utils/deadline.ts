import { TZDate } from "@date-fns/tz";
import {
  differenceInCalendarDays,
  endOfDay,
  getMonth,
  isAfter,
  isBefore,
  isWithinInterval,
  setDate,
  startOfDay,
} from "date-fns";

export const DEADLINE_DAY = 5;

/**
 * Residents are in Kyiv, so every date decision here is made in Kyiv regardless
 * of the device's timezone. The backend doesn't enforce the window, so this is the
 * only place the day 1-5 rule lives.
 */
export const KYIV_TZ = "Europe/Kyiv";

/** The current instant, as a Kyiv-zoned date. date-fns functions preserve the zone. */
export function kyivNow(): TZDate {
  return new TZDate(Date.now(), KYIV_TZ);
}

export type DeadlineStatus = "due" | "overdue" | "submitted" | "submitted-late";

export interface DeadlineRange {
  start: Date;
  end: Date;
}

export function getSubmitWindow(now: Date = kyivNow()): DeadlineRange {
  const kyiv = new TZDate(now, KYIV_TZ);
  return {
    start: startOfDay(setDate(kyiv, 1)),
    end: endOfDay(setDate(kyiv, DEADLINE_DAY)),
  };
}

/** Month the submit window closes in, not the billing period being reported on. */
export function getDeadlineMonthIndex(now: Date = kyivNow()): number {
  return getMonth(getSubmitWindow(now).end);
}

export function getDeadlineStatus(
  submittedAt: string | null | undefined
): DeadlineStatus {
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
  const windowClosed = isAfter(kyivNow(), window.end);

  if (!submittedAt) {
    return windowClosed;
  }

  return isBefore(submittedAt, window.start) && windowClosed;
}

export function isPending(submittedAt: string | null | undefined): boolean {
  const window = getSubmitWindow();

  if (!submittedAt) {
    return isWithinInterval(kyivNow(), window);
  }

  return isBefore(submittedAt, window.start);
}

export function getDaysLeft(): number {
  const { end } = getSubmitWindow();
  return differenceInCalendarDays(end, kyivNow());
}

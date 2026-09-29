import {
  differenceInCalendarDays,
  endOfDay,
  getMonth,
  isAfter,
  isBefore,
  isWithinInterval,
  setDate,
  startOfDay,
  startOfToday,
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

/**
 * `isOpen`, when given, is the server's authoritative answer (from
 * GET /billing/window, computed in Kyiv time) to whether today falls in the
 * submit window. Without it, openness falls back to comparing the device
 * clock against a window computed from the device's own local time -- which
 * can disagree with the server right at the boundary, or if the device clock
 * itself is wrong. Prefer passing it whenever the server window is available.
 */
export function getDeadlineStatus(
  submittedAt: string | null | undefined,
  isOpen?: boolean
): DeadlineStatus {
  const window = getSubmitWindow();

  if (isOverdue(submittedAt, isOpen)) {
    return "overdue";
  }

  if (isPending(submittedAt, isOpen)) {
    return "due";
  }

  // If the submission is not overdue and not pending, it means it has been submitted.
  return isWithinInterval(submittedAt!, window) ? "submitted" : "submitted-late";
}

export function isOverdue(submittedAt: string | null | undefined, isOpen?: boolean): boolean {
  const window = getSubmitWindow();
  const windowClosed = isOpen === undefined ? isAfter(new Date(), window.end) : !isOpen;

  if (!submittedAt) {
    return windowClosed;
  }

  return isBefore(submittedAt, window.start) && windowClosed;
}

export function isPending(submittedAt: string | null | undefined, isOpen?: boolean): boolean {
  const window = getSubmitWindow();

  if (!submittedAt) {
    return isOpen === undefined ? isWithinInterval(new Date(), window) : isOpen;
  }

  return isBefore(submittedAt, window.start);
}

export function getDaysLeft(): number {
  const { end } = getSubmitWindow();
  return differenceInCalendarDays(end, startOfToday());
}

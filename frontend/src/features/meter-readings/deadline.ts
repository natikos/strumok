import {
  differenceInDays,
  endOfDay,
  isAfter,
  isBefore,
  isWithinInterval,
  setDate,
  startOfDay,
} from "date-fns";

export const DEADLINE_DAY = 5;

export type DeadlineStatus = "due" | "overdue" | "submitted" | "submitted-late";

export interface DeadlineRange {
  start: Date;
  end: Date;
}

export function getSubmitWindow(): DeadlineRange {
  return {
    start: startOfDay(setDate(new Date(), 1)),
    end: endOfDay(setDate(new Date(), DEADLINE_DAY)),
  };
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
  const today = startOfDay(new Date());
  const { end } = getSubmitWindow();

  return Math.max(0, differenceInDays(end, today));
}

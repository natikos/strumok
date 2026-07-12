export const DEADLINE_DAY = 5;

export type DeadlineStatus = "on-time" | "overdue" | "submitted" | "submitted-late";

export function getSubmitDeadline(): Date {
  const now = new Date();
  now.setDate(DEADLINE_DAY);
  return now;
}

export function getDeadlineStatus(submittedAt: string | null | undefined): DeadlineStatus {
  const today = new Date();
  const isAfterDeadline = today.getDate() > DEADLINE_DAY;

  if (!submittedAt) {
    return isAfterDeadline ? "overdue" : "on-time";
  }

  const submittedDate = new Date(submittedAt);
  const submittedDay = submittedDate.getDate();

  return submittedDay > DEADLINE_DAY ? "submitted-late" : "submitted";
}

export function getDaysLeft(): number {
  const today = new Date();
  const deadline = getSubmitDeadline();
  const diffMs = deadline.getTime() - today.getTime();
  return Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));
}

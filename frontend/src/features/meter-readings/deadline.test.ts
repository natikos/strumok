import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getDaysLeft, getDeadlineStatus, getSubmitWindow, isOverdue, isPending } from "./deadline";

/**
 * `now` is always constructed from local components (`new Date(y, m, d, ...)`),
 * never a UTC ISO string, so these assertions don't flip depending on the CI
 * runner's timezone.
 */
function freezeAt(
  [year, monthIndex, day]: [year: number, monthIndex: number, day: number],
  hour = 12
): void {
  vi.setSystemTime(new Date(year, monthIndex, day, hour, 0, 0));
}

describe("getSubmitWindow", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("spans day 1 00:00:00 to day 5 23:59:59 of the current month", () => {
    freezeAt([2026, 6, 15]); // July 15, 2026 -- window is for July regardless of "today".

    const { start, end } = getSubmitWindow();

    expect(start).toEqual(new Date(2026, 6, 1, 0, 0, 0, 0));
    expect(end.getDate()).toBe(5);
    expect(end.getHours()).toBe(23);
    expect(end.getMinutes()).toBe(59);
    expect(end.getSeconds()).toBe(59);
  });

  it("stays within January when frozen in January (no year underflow)", () => {
    freezeAt([2026, 0, 3]);

    const { start, end } = getSubmitWindow();

    expect(start).toEqual(new Date(2026, 0, 1, 0, 0, 0, 0));
    expect(end.getMonth()).toBe(0);
    expect(end.getFullYear()).toBe(2026);
  });

  it("stays within December when frozen in December (no year overflow)", () => {
    freezeAt([2026, 11, 3]);

    const { start, end } = getSubmitWindow();

    expect(start).toEqual(new Date(2026, 11, 1, 0, 0, 0, 0));
    expect(end.getMonth()).toBe(11);
    expect(end.getFullYear()).toBe(2026);
  });
});

describe("getDeadlineStatus", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("is due when nothing submitted and today is within the window (day 1)", () => {
    freezeAt([2026, 6, 1]);
    expect(getDeadlineStatus(null)).toBe("due");
  });

  it("is due when nothing submitted and today is within the window (day 5)", () => {
    freezeAt([2026, 6, 5], 23);
    expect(getDeadlineStatus(null)).toBe("due");
  });

  it("is overdue when nothing submitted and today is day 6", () => {
    freezeAt([2026, 6, 6], 0);
    expect(getDeadlineStatus(null)).toBe("overdue");
  });

  it("is overdue when nothing submitted after the window in a later month", () => {
    freezeAt([2026, 6, 20]);
    expect(getDeadlineStatus(undefined)).toBe("overdue");
  });

  it("is submitted when submittedAt falls within this month's window", () => {
    freezeAt([2026, 6, 3]);
    expect(getDeadlineStatus(new Date(2026, 6, 2, 9, 0).toISOString())).toBe("submitted");
  });

  it("is submitted-late when submittedAt falls after this month's window", () => {
    freezeAt([2026, 6, 20]);
    expect(getDeadlineStatus(new Date(2026, 6, 10, 9, 0).toISOString())).toBe("submitted-late");
  });

  it("treats a submission from a prior period as overdue once past this month's deadline", () => {
    // A resident who submitted June's reading on time, and now it's past July's
    // deadline with nothing submitted for July: the prior submittedAt predates
    // this month's window start, so isOverdue's own branch fires.
    freezeAt([2026, 6, 20]);
    expect(getDeadlineStatus(new Date(2026, 5, 3, 9, 0).toISOString())).toBe("overdue");
  });

  it("treats a submission from a prior period as due while still inside this month's window", () => {
    freezeAt([2026, 6, 3]);
    expect(getDeadlineStatus(new Date(2026, 5, 3, 9, 0).toISOString())).toBe("due");
  });
});

describe("isOverdue", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("is false with nothing submitted while still inside the window", () => {
    freezeAt([2026, 6, 5], 23);
    expect(isOverdue(null)).toBe(false);
  });

  it("is true with nothing submitted once the window has closed", () => {
    freezeAt([2026, 6, 6], 0);
    expect(isOverdue(null)).toBe(true);
  });

  it("is false for a submission made within the current window even after it closes", () => {
    freezeAt([2026, 6, 20]);
    expect(isOverdue(new Date(2026, 6, 3, 9, 0).toISOString())).toBe(false);
  });

  it("is true for a submission that predates the window once the window has closed", () => {
    freezeAt([2026, 6, 20]);
    expect(isOverdue(new Date(2026, 5, 3, 9, 0).toISOString())).toBe(true);
  });
});

describe("isPending", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("is true with nothing submitted while inside the window", () => {
    freezeAt([2026, 6, 1]);
    expect(isPending(null)).toBe(true);
  });

  it("is false with nothing submitted once the window has closed", () => {
    freezeAt([2026, 6, 6]);
    expect(isPending(null)).toBe(false);
  });

  it("is true when a submission predates the current window (regardless of today)", () => {
    freezeAt([2026, 6, 3]);
    expect(isPending(new Date(2026, 5, 3, 9, 0).toISOString())).toBe(true);
  });

  it("is false when a submission falls within the current window", () => {
    freezeAt([2026, 6, 3]);
    expect(isPending(new Date(2026, 6, 2, 9, 0).toISOString())).toBe(false);
  });
});

describe("getDaysLeft", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("counts down to day 5 of the current month", () => {
    freezeAt([2026, 6, 1]);
    expect(getDaysLeft()).toBe(4);
  });

  it("is zero on deadline day itself", () => {
    freezeAt([2026, 6, 5]);
    expect(getDaysLeft()).toBe(0);
  });

  it("never goes negative once the window has passed", () => {
    freezeAt([2026, 6, 20]);
    expect(getDaysLeft()).toBe(0);
  });
});

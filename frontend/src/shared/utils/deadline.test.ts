import { TZDate } from "@date-fns/tz";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getDaysLeft,
  getDeadlineMonthIndex,
  getDeadlineStatus,
  getSubmitWindow,
  isOverdue,
  isPending,
  KYIV_TZ,
} from "./deadline";

/**
 * Instants are built from Kyiv wall-clock components, since that's the zone the
 * deadline logic works in. They never depend on the runner's own timezone.
 */
function kyiv([year, monthIndex, day]: [number, number, number], hour = 0): TZDate {
  return new TZDate(year, monthIndex, day, hour, 0, 0, KYIV_TZ);
}

function freezeAt(
  [year, monthIndex, day]: [year: number, monthIndex: number, day: number],
  hour = 12
): void {
  vi.setSystemTime(kyiv([year, monthIndex, day], hour));
}

describe("getSubmitWindow", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("spans day 1 00:00:00 to day 5 23:59:59 of the current month", () => {
    freezeAt([2026, 6, 15]); // July 15, 2026 -- window is for July regardless of "today".

    const { start, end } = getSubmitWindow();

    expect(start.getTime()).toBe(kyiv([2026, 6, 1]).getTime());
    expect(end.getDate()).toBe(5);
    expect(end.getHours()).toBe(23);
    expect(end.getMinutes()).toBe(59);
    expect(end.getSeconds()).toBe(59);
  });

  it("stays within January when frozen in January (no year underflow)", () => {
    freezeAt([2026, 0, 3]);

    const { start, end } = getSubmitWindow();

    expect(start.getTime()).toBe(kyiv([2026, 0, 1]).getTime());
    expect(end.getMonth()).toBe(0);
    expect(end.getFullYear()).toBe(2026);
  });

  it("stays within December when frozen in December (no year overflow)", () => {
    freezeAt([2026, 11, 3]);

    const { start, end } = getSubmitWindow();

    expect(start.getTime()).toBe(kyiv([2026, 11, 1]).getTime());
    expect(end.getMonth()).toBe(11);
    expect(end.getFullYear()).toBe(2026);
  });

  it("does not mutate the date it is given", () => {
    const now = kyiv([2026, 8, 17]);

    getSubmitWindow(now);

    expect(now.getTime()).toBe(kyiv([2026, 8, 17]).getTime());
  });
});

describe("getDeadlineMonthIndex", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("names the month the window closes in, not the period being reported on", () => {
    freezeAt([2026, 8, 17]);

    expect(getDeadlineMonthIndex()).toBe(8);
  });

  it("names the current month while the window is still open", () => {
    freezeAt([2026, 8, 3]);

    expect(getDeadlineMonthIndex()).toBe(8);
  });

  it("stays in month on a 31st, where naive date arithmetic would overflow", () => {
    freezeAt([2026, 2, 31]);

    expect(getDeadlineMonthIndex()).toBe(2);
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
    expect(getDeadlineStatus(kyiv([2026, 6, 2], 9).toISOString())).toBe("submitted");
  });

  it("is submitted-late when submittedAt falls after this month's window", () => {
    freezeAt([2026, 6, 20]);
    expect(getDeadlineStatus(kyiv([2026, 6, 10], 9).toISOString())).toBe("submitted-late");
  });

  it("treats a submission from a prior period as overdue once past this month's deadline", () => {
    // A resident who submitted June's reading on time, and now it's past July's
    // deadline with nothing submitted for July: the prior submittedAt predates
    // this month's window start, so isOverdue's own branch fires.
    freezeAt([2026, 6, 20]);
    expect(getDeadlineStatus(kyiv([2026, 5, 3], 9).toISOString())).toBe("overdue");
  });

  it("treats a submission from a prior period as due while still inside this month's window", () => {
    freezeAt([2026, 6, 3]);
    expect(getDeadlineStatus(kyiv([2026, 5, 3], 9).toISOString())).toBe("due");
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
    expect(isOverdue(kyiv([2026, 6, 3], 9).toISOString())).toBe(false);
  });

  it("is true for a submission that predates the window once the window has closed", () => {
    freezeAt([2026, 6, 20]);
    expect(isOverdue(kyiv([2026, 5, 3], 9).toISOString())).toBe(true);
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
    expect(isPending(kyiv([2026, 5, 3], 9).toISOString())).toBe(true);
  });

  it("is false when a submission falls within the current window", () => {
    freezeAt([2026, 6, 3]);
    expect(isPending(kyiv([2026, 6, 2], 9).toISOString())).toBe(false);
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

  it("goes negative once the window has passed", () => {
    freezeAt([2026, 6, 20]);
    expect(getDaysLeft()).toBe(-15);
  });
});

/**
 * Residents are in Kyiv (UTC+2/+3), and the API sends `submitted_at` as UTC with a
 * `Z` suffix (#142). These run with the process in a far-off timezone to prove the
 * result follows Kyiv time, not the device's; CI runs in UTC, where a UTC/local
 * mix-up would be invisible.
 */
describe("deadline logic with the device outside Kyiv", () => {
  const originalTz = process.env["TZ"];

  beforeAll(() => {
    process.env["TZ"] = "America/Los_Angeles";
  });
  afterAll(() => {
    if (originalTz === undefined) {
      delete process.env["TZ"];
    } else {
      process.env["TZ"] = originalTz;
    }
  });
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("runs with a non-Kyiv device offset (guards the rest of this block)", () => {
    expect(new Date(2026, 6, 5).getTimezoneOffset()).toBe(420);
  });

  it("is still due at 23:30 Kyiv on day 5, though it's already day 5 afternoon in LA", () => {
    vi.setSystemTime("2026-07-05T20:30:00Z");
    expect(getDeadlineStatus(null)).toBe("due");
  });

  it("is overdue at 00:30 Kyiv on day 6, though it's still day 5 evening in LA", () => {
    vi.setSystemTime("2026-07-05T21:30:00Z");
    expect(getDeadlineStatus(null)).toBe("overdue");
  });

  it("names the Kyiv month at 00:30 Kyiv on the 1st, still the prior month in LA", () => {
    vi.setSystemTime("2026-06-30T21:30:00Z");
    expect(getDeadlineMonthIndex()).toBe(6);
  });

  it("is submitted for a reading at 23:30 Kyiv on day 5", () => {
    freezeAt([2026, 6, 6]);
    expect(getDeadlineStatus("2026-07-05T20:30:00Z")).toBe("submitted");
  });

  it("is submitted-late for a reading at 00:30 Kyiv on day 6", () => {
    freezeAt([2026, 6, 6]);
    expect(getDeadlineStatus("2026-07-05T21:30:00Z")).toBe("submitted-late");
  });

  it("is submitted for a reading at 00:30 Kyiv on day 1, still the prior UTC day", () => {
    freezeAt([2026, 6, 3]);
    expect(getDeadlineStatus("2026-06-30T21:30:00Z")).toBe("submitted");
  });
});

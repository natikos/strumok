import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { currentBillingPeriod, formatPeriodMonth, periodToDate } from "./billing-period";

describe("currentBillingPeriod", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("is the prior month once it is the 1st in Kyiv, even while still the 30th in UTC", () => {
    // 2026-06-30 22:00 UTC is 2026-07-01 01:00 in Kyiv (EEST).
    vi.setSystemTime("2026-06-30T22:00:00Z");

    expect(currentBillingPeriod()).toBe("2026-06");
  });

  it("is still two months back one second before midnight Kyiv on the 1st", () => {
    vi.setSystemTime("2026-06-30T20:59:59Z");

    expect(currentBillingPeriod()).toBe("2026-05");
  });
});

describe("periodToDate", () => {
  it("returns the first day of the month in local time", () => {
    const date = periodToDate("2026-08");
    expect([date.getFullYear(), date.getMonth(), date.getDate()]).toEqual([2026, 7, 1]);
  });
});

describe("formatPeriodMonth", () => {
  it("formats the month in the given locale", () => {
    expect(formatPeriodMonth("2026-08", "en-US")).toBe("August");
    expect(formatPeriodMonth("2026-08", "uk-UA")).toBe("серпень");
  });

  it("accepts custom options", () => {
    expect(formatPeriodMonth("2026-08", "en-US", { month: "long", year: "numeric" })).toBe(
      "August 2026"
    );
  });
});

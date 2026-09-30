import { describe, expect, it } from "vitest";

import { formatPeriodMonth, periodToDate } from "./billing-period";

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

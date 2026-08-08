import { describe, expect, it } from "vitest";

import { formatMeterValue } from "./format";

describe("formatMeterValue", () => {
  it("returns an em dash for null", () => {
    expect(formatMeterValue(null, "en-US")).toBe("—");
  });

  it("returns an em dash for undefined", () => {
    expect(formatMeterValue(undefined, "en-US")).toBe("—");
  });

  it("formats a numeric value using the given locale", () => {
    expect(formatMeterValue(1234.5, "en-US")).toBe("1,234.5");
  });

  it("formats a string value by converting it to a number first", () => {
    expect(formatMeterValue("1234.5", "en-US")).toBe("1,234.5");
  });

  it("rounds to a maximum of two fraction digits", () => {
    expect(formatMeterValue(1234.5678, "en-US")).toBe("1,234.57");
  });

  it("formats using a different locale's grouping and decimal separators", () => {
    expect(formatMeterValue(1234.5, "uk-UA")).toBe("1 234,5");
  });
});

import { describe, expect, it } from "vitest";

import { householdReference, paymentPurpose } from "./paymentPurpose";

describe("paymentPurpose", () => {
  it("formats a household reference", () => {
    expect(householdReference(7)).toBe("STR-7");
  });

  it("lists every household reference, sorted", () => {
    expect(paymentPurpose("Electricity", [9, 2])).toBe("Electricity STR-2, STR-9");
  });

  it("falls back to the label alone", () => {
    expect(paymentPurpose("Electricity", [])).toBe("Electricity");
  });
});

import { describe, expect, it } from "vitest";

import { capitalize, toCamelCase } from "./string";

describe("toCamelCase", () => {
  it("converts a single hyphenated segment to camelCase", () => {
    expect(toCamelCase("no-household")).toBe("noHousehold");
  });

  it("converts multiple hyphens across a longer string", () => {
    expect(toCamelCase("period-already-submitted")).toBe("periodAlreadySubmitted");
  });

  it("returns the string unchanged when there are no hyphens to convert", () => {
    expect(toCamelCase("unauthorized")).toBe("unauthorized");
  });

  it("returns an empty string unchanged", () => {
    expect(toCamelCase("")).toBe("");
  });

  it("leaves a trailing hyphen with no following letter untouched", () => {
    expect(toCamelCase("trailing-")).toBe("trailing-");
  });

  it("does not touch a hyphen followed by an uppercase or non-letter character", () => {
    expect(toCamelCase("household-1")).toBe("household-1");
  });
});

describe("capitalize", () => {
  it("uppercases the first letter of a lowercase word", () => {
    expect(capitalize("household")).toBe("Household");
  });

  it("leaves an already-capitalized word unchanged", () => {
    expect(capitalize("Household")).toBe("Household");
  });

  it("returns an empty string unchanged rather than throwing", () => {
    expect(capitalize("")).toBe("");
  });

  it("does not alter a single character beyond casing it", () => {
    expect(capitalize("a")).toBe("A");
  });

  it("only capitalizes the first character, leaving the rest of the casing as-is", () => {
    expect(capitalize("gARDEN")).toBe("GARDEN");
  });
});

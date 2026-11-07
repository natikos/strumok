import { beforeEach, describe, expect, it, vi } from "vitest";

import { clearReadingDraft, loadReadingDraft, saveReadingDraft } from "./useReadingDraft";

describe("reading draft", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("round-trips the entered values for the same household and period", () => {
    saveReadingDraft(1, { period: "2026-10", day: 120.5, night: null });

    expect(loadReadingDraft(1, "2026-10")).toEqual({ period: "2026-10", day: 120.5, night: null });
    expect(loadReadingDraft(2, "2026-10")).toBeNull();
  });

  it("discards a draft from an earlier period", () => {
    saveReadingDraft(1, { period: "2026-09", day: 1, night: 2 });

    expect(loadReadingDraft(1, "2026-10")).toBeNull();
    expect(localStorage.getItem("strumok:reading-draft:1")).toBeNull();
  });

  it("forgets the draft once both fields are empty or it is cleared", () => {
    saveReadingDraft(1, { period: "2026-10", day: 1, night: 2 });
    saveReadingDraft(1, { period: "2026-10", day: null, night: null });
    expect(loadReadingDraft(1, "2026-10")).toBeNull();

    saveReadingDraft(1, { period: "2026-10", day: 1, night: 2 });
    clearReadingDraft(1);
    expect(loadReadingDraft(1, "2026-10")).toBeNull();
  });

  it("ignores corrupt JSON", () => {
    localStorage.setItem("strumok:reading-draft:1", "{nope");

    expect(loadReadingDraft(1, "2026-10")).toBeNull();
  });

  it("never throws when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(() => saveReadingDraft(1, { period: "2026-10", day: 1, night: 2 })).not.toThrow();
    expect(loadReadingDraft(1, "2026-10")).toBeNull();

    vi.restoreAllMocks();
  });
});

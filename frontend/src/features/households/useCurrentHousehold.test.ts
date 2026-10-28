import { beforeEach, describe, expect, it, vi } from "vitest";

describe("useCurrentHousehold.setHouseholds", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.resetModules();
  });

  async function load() {
    return (await import("./useCurrentHousehold")).useCurrentHousehold();
  }

  it("reports the switch when the remembered household is no longer listed", async () => {
    window.localStorage.setItem("strumok:current-household-id", "1");
    window.localStorage.setItem("strumok:current-household-name", "Plot 1");
    const { setHouseholds, currentId } = await load();

    const change = setHouseholds([{ id: 2, name: "Plot 2" }]);

    expect(change).toEqual({ removedName: "Plot 1", switchedTo: { id: 2, name: "Plot 2" } });
    expect(currentId.value).toBe(2);
  });

  it("reports nothing when the current household is still listed or none was remembered", async () => {
    const { setHouseholds } = await load();
    expect(setHouseholds([{ id: 2, name: "Plot 2" }])).toBeNull();

    window.localStorage.setItem("strumok:current-household-id", "2");
    expect(setHouseholds([{ id: 2, name: "Plot 2" }])).toBeNull();
  });
});

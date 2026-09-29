import { flushPromises } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BillingWindowOut } from "@shared/api/billing";

const { getBillingWindow } = vi.hoisted(() => ({
  getBillingWindow: vi.fn(),
}));

vi.mock("@shared/api/billing", () => ({ getBillingWindow }));

function makeWindow(overrides: Partial<BillingWindowOut> = {}): BillingWindowOut {
  return {
    period: "2026-06",
    opens_at: "2026-07-01T00:00:00Z",
    closes_at: "2026-07-05T23:59:59.999999Z",
    is_open: true,
    ...overrides,
  };
}

describe("useBillingWindow", () => {
  beforeEach(() => {
    getBillingWindow.mockReset();
    localStorage.clear();
    vi.resetModules();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("populates the window from a successful fetch", async () => {
    const { useBillingWindow } = await import("./useBillingWindow");
    getBillingWindow.mockResolvedValue(makeWindow({ period: "2026-08", is_open: false }));

    const { window: billingWindow, load } = useBillingWindow();
    await load();
    await flushPromises();

    expect(billingWindow.value).toEqual(makeWindow({ period: "2026-08", is_open: false }));
  });

  it("keeps the previously loaded window in place when a later fetch fails", async () => {
    // A resident whose connection drops after the dashboard already loaded
    // once must keep seeing the last known deadline state, not lose it.
    const { useBillingWindow } = await import("./useBillingWindow");
    getBillingWindow.mockResolvedValueOnce(makeWindow({ period: "2026-06" }));

    const { window: billingWindow, load } = useBillingWindow();
    await load();
    await flushPromises();
    expect(billingWindow.value?.period).toBe("2026-06");

    getBillingWindow.mockRejectedValueOnce(new Error("network down"));
    await load();
    await flushPromises();

    expect(billingWindow.value?.period).toBe("2026-06");
  });

  it("falls back to a cached window from localStorage when the very first fetch fails", async () => {
    // A resident opening the app offline should still see the last window
    // that was cached on a previous, successful visit.
    localStorage.setItem(
      "strumok:billing-window",
      JSON.stringify(makeWindow({ period: "2026-05" }))
    );
    const { useBillingWindow } = await import("./useBillingWindow");
    getBillingWindow.mockRejectedValueOnce(new Error("offline"));

    const { window: billingWindow, load } = useBillingWindow();
    expect(billingWindow.value?.period).toBe("2026-05");

    await load();
    await flushPromises();

    expect(billingWindow.value?.period).toBe("2026-05");
  });
});

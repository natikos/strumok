import { flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

import type { MeterReadingOut } from "@shared/api/meter-readings";

const { getCurrentPeriod, listStatements } = vi.hoisted(() => ({
  getCurrentPeriod: vi.fn(),
  listStatements: vi.fn(),
}));

vi.mock("@shared/api/billing", () => ({ getCurrentPeriod, listStatements }));

import { useCurrentPeriodState } from "./useCurrentPeriodState";

const estimateReading = { period: "2026-09", source: "estimate" } as MeterReadingOut;

describe("useCurrentPeriodState", () => {
  beforeEach(() => {
    getCurrentPeriod.mockReset();
    listStatements.mockReset();
  });

  it("stays open and fetches nothing else while the period is open", async () => {
    getCurrentPeriod.mockResolvedValue({ period: "2026-09", status: "open" });
    const state = useCurrentPeriodState(ref([]), ref(1));

    await state.load();

    expect(state.isClosed.value).toBe(false);
    expect(listStatements).not.toHaveBeenCalled();
  });

  it("reports an estimate with its usage and total once the period is closed", async () => {
    getCurrentPeriod.mockResolvedValue({ period: "2026-09", status: "closed" });
    listStatements.mockResolvedValue([
      { day_usage_kwh: "40.00", is_estimated: true, night_usage_kwh: "10.00", period: "2026-09", total_uah: "169.00" },
    ]);
    const state = useCurrentPeriodState(ref([estimateReading]), ref(1));

    await state.load();
    await flushPromises();

    expect(state.isClosed.value).toBe(true);
    expect(state.isEstimated.value).toBe(true);
    expect(state.estimate.value).toEqual({ totalUah: 169, usageKwh: 50 });
  });

  it("falls back to an open form when the status can't be loaded", async () => {
    getCurrentPeriod.mockRejectedValue(new Error("offline"));
    const state = useCurrentPeriodState(ref([]), ref(1));

    await state.load();

    expect(state.isClosed.value).toBe(false);
  });
});

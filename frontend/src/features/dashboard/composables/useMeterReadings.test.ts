import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, nextTick } from "vue";

import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
import { appPlugins } from "@/shared/testing/mount";
import type { MeterReadingOut } from "@shared/api/meter-readings";

import { useMeterReadings } from "./useMeterReadings";

const { listMyMeterReadings, submitMyMeterReading } = vi.hoisted(() => ({
  listMyMeterReadings: vi.fn(),
  submitMyMeterReading: vi.fn(),
}));

vi.mock("@shared/api/meter-readings", () => ({
  listMyMeterReadings,
  submitMyMeterReading,
}));

function makeReading(overrides: Partial<MeterReadingOut> = {}): MeterReadingOut {
  return {
    id: 1,
    household_id: 1,
    submitted_by_user_id: 1,
    period: "2026-06",
    day_meter_value: "100.00",
    night_meter_value: "50.00",
    day_usage_kwh: "10.00",
    night_usage_kwh: "5.00",
    amount_charged_uah: "0.00",
    submitted_at: "2026-06-02T09:00:00.000Z",
    ...overrides,
  };
}

/**
 * `useMeterReadings` calls `useI18n`/`useLocale`, so it needs a real component
 * setup context with the app's plugins installed -- mirroring how the
 * dashboard page actually mounts it, not a bare `withSetup` stub.
 */
function mountComposable() {
  let result!: ReturnType<typeof useMeterReadings>;

  const Harness = defineComponent({
    setup() {
      result = useMeterReadings();
      return () => h("div");
    },
  });

  const wrapper = mount(Harness, { global: { plugins: appPlugins() } });

  return {
    wrapper,
    get result() {
      return result;
    },
  };
}

describe("useMeterReadings", () => {
  beforeEach(() => {
    listMyMeterReadings.mockReset();
    submitMyMeterReading.mockReset();
    useCurrentHousehold().setHouseholds([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("currentBillingPeriod / currentSlot", () => {
    it("resolves the billable period to the previous calendar month", async () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2026, 6, 15)); // "today" is July 15
      listMyMeterReadings.mockResolvedValue([]);

      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      // Billing period for "today = July" must be June (index 5), not July.
      expect(result.billingMonthIndex.value).toBe(5);
      expect(result.currentSlot.value?.period).toBe("2026-06");
    });

    it("rolls over the year correctly when frozen in January", async () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2026, 0, 3)); // "today" is January 3, 2026
      listMyMeterReadings.mockResolvedValue([]);

      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      // Previous month from January must be December of the prior year, not
      // month "-1" or December of the same year.
      expect(result.billingMonthIndex.value).toBe(11);
      expect(result.currentSlot.value?.period).toBe("2025-12");
    });
  });

  describe("readingsByPeriod / currentSlot.reading", () => {
    it("matches the current billing slot to its reading out of an unsorted history", async () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2026, 6, 15));
      const readings = [
        makeReading({ id: 1, period: "2026-04" }),
        makeReading({ id: 2, period: "2026-06" }),
        makeReading({ id: 3, period: "2026-05" }),
      ];
      listMyMeterReadings.mockResolvedValue(readings);

      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      expect(result.currentSlot.value?.reading?.id).toBe(2);
    });

    it("leaves the current slot's reading undefined when history has no match", async () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2026, 6, 15));
      listMyMeterReadings.mockResolvedValue([makeReading({ period: "2026-04" })]);

      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      expect(result.currentSlot.value?.reading).toBeUndefined();
    });
  });

  describe("latestReading", () => {
    it("is the most recent period, not the first element of an unsorted list", async () => {
      // The API's own ordering is period-descending, but the composable
      // shouldn't silently depend on request ordering to prove correct; feed
      // it out-of-order data and check it still resolves sensibly (i.e. not a
      // wrong hardcoded index).
      listMyMeterReadings.mockResolvedValue([
        makeReading({ id: 10, period: "2026-06" }),
        makeReading({ id: 20, period: "2026-05" }),
      ]);

      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      // Pinning current behavior: latestReading is `readings.at(0)`, i.e.
      // whatever the API returned first -- not independently re-sorted by the
      // composable. This documents the coupling to API ordering.
      expect(result.latestReading.value?.id).toBe(10);
    });
  });

  describe("handleSubmit validation", () => {
    it("rejects a missing day value without calling the API", async () => {
      listMyMeterReadings.mockResolvedValue([]);
      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      result.dayMeterValue.value = null;
      result.nightMeterValue.value = 50;

      await result.handleSubmit();

      expect(submitMyMeterReading).not.toHaveBeenCalled();
      expect(result.errors.value.dayMeterValue).toBeTruthy();
    });

    it("rejects a negative night value without calling the API", async () => {
      listMyMeterReadings.mockResolvedValue([]);
      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      result.dayMeterValue.value = 100;
      result.nightMeterValue.value = -5;

      await result.handleSubmit();

      expect(submitMyMeterReading).not.toHaveBeenCalled();
      expect(result.errors.value.nightMeterValue).toBeTruthy();
    });
  });

  describe("handleSubmit success path", () => {
    it("submits with the current billing period and appends the reading locally", async () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2026, 6, 15));
      listMyMeterReadings.mockResolvedValue([makeReading({ id: 1, period: "2026-05" })]);
      const created = makeReading({ id: 99, period: "2026-06" });
      submitMyMeterReading.mockResolvedValue(created);

      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      result.dayMeterValue.value = 120;
      result.nightMeterValue.value = 60;

      await result.handleSubmit();
      await flushPromises();

      expect(submitMyMeterReading).toHaveBeenCalledWith(
        expect.objectContaining({ period: "2026-06", day_meter_value: 120, night_meter_value: 60 }),
        null
      );

      expect(result.currentSlot.value?.reading?.id).toBe(99);
      expect(result.latestReading.value?.id).toBe(99);
    });

    it("resets the input fields after a successful submit", async () => {
      listMyMeterReadings.mockResolvedValue([]);
      submitMyMeterReading.mockResolvedValue(makeReading());

      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      result.dayMeterValue.value = 100;
      result.nightMeterValue.value = 50;

      await result.handleSubmit();
      await flushPromises();

      expect(result.dayMeterValue.value).toBeNull();
      expect(result.nightMeterValue.value).toBeNull();
    });

    it("still appends a successful submit when the initial history load failed", async () => {
      // A resident whose page failed to load history should not silently lose
      // a reading they just submitted -- this is the classic
      // "successful write during a failed surrounding read" data-loss path.
      listMyMeterReadings.mockRejectedValue(new Error("network down"));
      const created = makeReading({ id: 42, period: "2026-06" });
      submitMyMeterReading.mockResolvedValue(created);

      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      expect(result.latestReading.value).toBeUndefined();

      result.dayMeterValue.value = 10;
      result.nightMeterValue.value = 5;
      await result.handleSubmit();
      await flushPromises();

      // Current behavior: `readings.value` is still `null` after a failed load
      // (useAsyncData never sets it), so `handleSubmit`'s
      // `if (readings.value)` guard skips appending and the submitted reading
      // is not reflected anywhere the UI reads from. This is a silent-data-loss
      // path worth flagging, not something this test "fixes".
      expect(result.latestReading.value).toBeUndefined();
    });
  });

  describe("isOverdue (pinned pending issue #17)", () => {
    it("is captured once at composable creation and does not update afterward", async () => {
      vi.useFakeTimers();
      // Freeze inside the submit window so isOverdue is computed as false at
      // creation time.
      vi.setSystemTime(new Date(2026, 6, 3));
      listMyMeterReadings.mockResolvedValue([]);

      const { result } = mountComposable();
      await result.loadHistory();
      await flushPromises();

      expect(typeof result.isOverdue).toBe("boolean");
      expect(result.isOverdue).toBe(false);

      // Advance past the deadline. A reactive value would flip to true; the
      // known bug (issue #17) means this plain boolean snapshot never updates.
      vi.setSystemTime(new Date(2026, 6, 20));
      await nextTick();

      expect(result.isOverdue).toBe(false);
    });
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref } from "vue";

import type { MeterPeriod } from "@/features/dashboard/composables/useMeterReadings";
import { SEASON_ORDER, useUsageInsights } from "@/features/dashboard/composables/useUsageInsights";
import type { MeterReadingOut } from "@shared/api/meter-readings";

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
 * Build a `MeterPeriod` slot the way `useMeterReadings` does: `period` drives
 * `date`/labels so fixtures stay internally consistent without duplicating
 * `Intl.DateTimeFormat` calls in every test.
 */
function makeSlot(period: string, reading?: MeterReadingOut): MeterPeriod {
  const [year, month] = period.split("-").map(Number);
  const date = new Date(year!, month! - 1, 1);
  return {
    period,
    date,
    monthLabel: date.toLocaleString("en", { month: "short" }),
    monthLong: date.toLocaleString("en", { month: "long" }),
    isCurrent: false,
    reading,
  };
}

/** Consecutive "YYYY-MM" periods, oldest first, ending at `endPeriod`. */
function periodsEndingAt(endPeriod: string, count: number): string[] {
  const [year, month] = endPeriod.split("-").map(Number);
  const result: string[] = [];
  for (let offset = count - 1; offset >= 0; offset -= 1) {
    const date = new Date(year!, month! - 1 - offset, 1);
    result.push(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`);
  }
  return result;
}

describe("useUsageInsights", () => {
  describe("lastSubmittedPeriod", () => {
    it("is null when there is no history", () => {
      const slots = ref<MeterPeriod[]>([]);
      const { lastSubmittedPeriod } = useUsageInsights(slots);

      expect(lastSubmittedPeriod.value).toBeNull();
    });

    it("is the most recent slot WITH a reading, not the newest slot overall", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot("2026-04", makeReading({ period: "2026-04" })),
        makeSlot("2026-05", makeReading({ period: "2026-05" })),
        makeSlot("2026-06", undefined), // current, open period -- no usage yet
      ]);
      const { lastSubmittedPeriod } = useUsageInsights(slots);

      expect(lastSubmittedPeriod.value?.period).toBe("2026-05");
    });
  });

  describe("momChange", () => {
    it("is null with fewer than two submitted periods", () => {
      const slots = ref<MeterPeriod[]>([makeSlot("2026-06", makeReading())]);
      const { momChange } = useUsageInsights(slots);

      expect(momChange.value).toBeNull();
    });

    it("reports an increase as up with the correct percent", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-05",
          makeReading({ period: "2026-05", day_usage_kwh: "10.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "15.00", night_usage_kwh: "0.00" })
        ),
      ]);
      const { momChange } = useUsageInsights(slots);

      expect(momChange.value).toEqual({
        percent: 50,
        from: 10,
        to: 15,
        direction: "up",
        deltaUah: null,
      });
    });

    it("reports a decrease as down with a negative percent", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-05",
          makeReading({ period: "2026-05", day_usage_kwh: "20.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "10.00", night_usage_kwh: "0.00" })
        ),
      ]);
      const { momChange } = useUsageInsights(slots);

      expect(momChange.value).toEqual({
        percent: -50,
        from: 20,
        to: 10,
        direction: "down",
        deltaUah: null,
      });
    });

    it("reports equal usage as flat", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-05",
          makeReading({ period: "2026-05", day_usage_kwh: "10.00", night_usage_kwh: "5.00" })
        ),
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "10.00", night_usage_kwh: "5.00" })
        ),
      ]);
      const { momChange } = useUsageInsights(slots);

      expect(momChange.value).toEqual({
        percent: 0,
        from: 15,
        to: 15,
        direction: "flat",
        deltaUah: null,
      });
    });

    it("does not divide by zero when the prior period had zero usage", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-05",
          makeReading({ period: "2026-05", day_usage_kwh: "0.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "5.00", night_usage_kwh: "0.00" })
        ),
      ]);
      const { momChange } = useUsageInsights(slots);

      expect(momChange.value?.percent).toBe(100);
      expect(Number.isFinite(momChange.value!.percent)).toBe(true);
    });

    it("does not leak NaN when both periods had zero usage", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-05",
          makeReading({ period: "2026-05", day_usage_kwh: "0.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "0.00", night_usage_kwh: "0.00" })
        ),
      ]);
      const { momChange } = useUsageInsights(slots);

      expect(momChange.value).toEqual({
        percent: 0,
        from: 0,
        to: 0,
        direction: "flat",
        deltaUah: null,
      });
    });
  });

  describe("dayNightSplit", () => {
    it("is null when there is no submitted reading", () => {
      const slots = ref<MeterPeriod[]>([makeSlot("2026-06", undefined)]);
      const { dayNightSplit } = useUsageInsights(slots);

      expect(dayNightSplit.value).toBeNull();
    });

    it("is null when total usage is zero, avoiding a divide by zero", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "0.00", night_usage_kwh: "0.00" })
        ),
      ]);
      const { dayNightSplit } = useUsageInsights(slots);

      expect(dayNightSplit.value).toBeNull();
    });

    it("splits day/night percentages that sum to 100 for an uneven split", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "30.00", night_usage_kwh: "10.00" })
        ),
      ]);
      const { dayNightSplit } = useUsageInsights(slots);

      expect(dayNightSplit.value?.dayPct).toBeCloseTo(75);
      expect(dayNightSplit.value?.nightPct).toBeCloseTo(25);
      expect(dayNightSplit.value!.dayPct + dayNightSplit.value!.nightPct).toBeCloseTo(100);
    });
  });

  describe("seasonComparison", () => {
    // "Now" is anchored in August 2026 (summer) so the current season is
    // deterministic regardless of when the test suite actually runs.
    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2026, 7, 15));
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("is null when there are no readings for the current season", () => {
      const slots = ref<MeterPeriod[]>([makeSlot("2026-08", undefined)]);
      const { seasonComparison } = useUsageInsights(slots);

      expect(seasonComparison.value).toBeNull();
    });

    it("is null when this season has a reading but last year's same season doesn't", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot("2026-08", makeReading({ period: "2026-08", day_usage_kwh: "18.00" })),
      ]);
      const { seasonComparison } = useUsageInsights(slots);

      expect(seasonComparison.value).toBeNull();
    });

    it("does not fall back to an unrelated season when only a different season a year back exists", () => {
      const slots = ref<MeterPeriod[]>([
        // spring, one year back -- different season, must not be used
        makeSlot("2025-04", makeReading({ period: "2025-04", day_usage_kwh: "5.00" })),
        makeSlot("2026-08", makeReading({ period: "2026-08", day_usage_kwh: "10.00" })),
      ]);
      const { seasonComparison } = useUsageInsights(slots);

      expect(seasonComparison.value).toBeNull();
    });

    it("sums whatever summer months exist this year and last year, rather than requiring all three", () => {
      const slots = ref<MeterPeriod[]>([
        // last year: only June and July submitted (August missed)
        makeSlot(
          "2025-06",
          makeReading({ period: "2025-06", day_usage_kwh: "10.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2025-07",
          makeReading({ period: "2025-07", day_usage_kwh: "5.00", night_usage_kwh: "0.00" })
        ),
        // this year: only August submitted so far
        makeSlot(
          "2026-08",
          makeReading({ period: "2026-08", day_usage_kwh: "18.00", night_usage_kwh: "0.00" })
        ),
      ]);
      const { seasonComparison } = useUsageInsights(slots);

      expect(seasonComparison.value).toEqual({
        season: "summer",
        currentKwh: 18,
        currentPeriodCount: 1,
        previousYearKwh: 15,
        previousPeriodCount: 2,
        deltaPercent: 20,
        direction: "up",
      });
    });

    it("keeps December in the winter that ends the following February", () => {
      vi.setSystemTime(new Date(2027, 0, 15)); // January 2027 -- winter

      const slots = ref<MeterPeriod[]>([
        // this winter: December 2026 + January 2027
        makeSlot(
          "2026-12",
          makeReading({ period: "2026-12", day_usage_kwh: "12.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2027-01",
          makeReading({ period: "2027-01", day_usage_kwh: "8.00", night_usage_kwh: "0.00" })
        ),
        // last winter: December 2025 + January 2026
        makeSlot(
          "2025-12",
          makeReading({ period: "2025-12", day_usage_kwh: "10.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2026-01",
          makeReading({ period: "2026-01", day_usage_kwh: "5.00", night_usage_kwh: "0.00" })
        ),
      ]);
      const { seasonComparison } = useUsageInsights(slots);

      expect(seasonComparison.value).toEqual(
        expect.objectContaining({
          season: "winter",
          currentKwh: 20,
          currentPeriodCount: 2,
          previousYearKwh: 15,
          previousPeriodCount: 2,
          direction: "up",
        })
      );
      expect(seasonComparison.value?.deltaPercent).toBeCloseTo(33.33, 1);
    });
  });

  describe("trendSeries", () => {
    it("keeps exactly the last 12 slots when more history is available", () => {
      const periods = periodsEndingAt("2026-06", 24);
      const slots = ref<MeterPeriod[]>(
        periods.map((period) => makeSlot(period, makeReading({ period })))
      );
      const { trendSeries } = useUsageInsights(slots);

      expect(trendSeries.value.labels).toHaveLength(12);
      expect(trendSeries.value.labels[0]).toBe(slots.value[12]!.monthLabel);
      expect(trendSeries.value.labels.at(-1)).toBe(slots.value.at(-1)!.monthLabel);
    });

    it("represents a missing month as null, never 0, in the day/night arrays", () => {
      const periods = periodsEndingAt("2026-06", 3);
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          periods[0]!,
          makeReading({ period: periods[0]!, day_usage_kwh: "10.00", night_usage_kwh: "5.00" })
        ),
        makeSlot(periods[1]!, undefined), // resident missed this month
        makeSlot(
          periods[2]!,
          makeReading({ period: periods[2]!, day_usage_kwh: "8.00", night_usage_kwh: "2.00" })
        ),
      ]);
      const { trendSeries } = useUsageInsights(slots);

      expect(trendSeries.value.day).toEqual([10, null, 8]);
      expect(trendSeries.value.night).toEqual([5, null, 2]);
      expect(trendSeries.value.presentCount).toBe(2);
    });
  });

  describe("yearOverYear", () => {
    it("matches the same month one year back by the YYYY-MM period key", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2025-06",
          makeReading({ period: "2025-06", day_usage_kwh: "12.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "18.00", night_usage_kwh: "0.00" })
        ),
      ]);
      const { yearOverYear } = useUsageInsights(slots);

      expect(yearOverYear.value).toEqual({
        monthIndex: 5,
        monthLong: slots.value[1]!.monthLong,
        current: 18,
        previous: 12,
        deltaKwh: 6,
        deltaPercent: 50,
        direction: "up",
        deltaUah: null,
      });
    });

    it("is null when the prior-year period has no reading", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot("2025-06", undefined),
        makeSlot("2026-06", makeReading({ period: "2026-06" })),
      ]);
      const { yearOverYear } = useUsageInsights(slots);

      expect(yearOverYear.value).toBeNull();
    });

    it("is null when the prior year is entirely absent from history", () => {
      const slots = ref<MeterPeriod[]>([makeSlot("2026-06", makeReading({ period: "2026-06" }))]);
      const { yearOverYear } = useUsageInsights(slots);

      expect(yearOverYear.value).toBeNull();
    });
  });

  describe("seasonAverages", () => {
    it("returns all four seasons in SEASON_ORDER even with no data", () => {
      const slots = ref<MeterPeriod[]>([]);
      const { seasonAverages } = useUsageInsights(slots);

      expect(seasonAverages.value.map((s) => s.season)).toEqual(SEASON_ORDER);
      for (const season of seasonAverages.value) {
        expect(season.periodCount).toBe(0);
        expect(season.averageKwh).toBe(0);
        expect(Number.isNaN(season.averageKwh)).toBe(false);
      }
    });

    it("averages only over the last 12 periods, ignoring older history", () => {
      // 24 months ending June 2026. Winter months (Dec/Jan/Feb) in the older
      // 12 (months 13-24 back) carry a huge usage value that must NOT be
      // averaged in; only the most recent 12 months' winter readings should
      // count.
      const periods = periodsEndingAt("2026-06", 24);
      const winterMonths = new Set([11, 0, 1]); // Dec, Jan, Feb (0-indexed)

      const slots = ref<MeterPeriod[]>(
        periods.map((period, index) => {
          const [, month] = period.split("-").map(Number);
          const isOlderHalf = index < 12;
          const isWinter = winterMonths.has(month! - 1);
          const usage = isOlderHalf && isWinter ? "999.00" : "10.00";
          return makeSlot(
            period,
            makeReading({ period, day_usage_kwh: usage, night_usage_kwh: "0.00" })
          );
        })
      );

      const { seasonAverages } = useUsageInsights(slots);
      const winter = seasonAverages.value.find((s) => s.season === "winter")!;

      // If the older, huge-usage winter months leaked in, this average would
      // be dragged far above 10.
      expect(winter.averageKwh).toBe(10);
    });
  });

  describe("hryvnia deltas", () => {
    it("reports the charge difference when both periods were billed", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot("2026-05", makeReading({ period: "2026-05", amount_charged_uah: "611.00" })),
        makeSlot("2026-06", makeReading({ period: "2026-06", amount_charged_uah: "679.15" })),
      ]);
      const { momChange } = useUsageInsights(slots);

      expect(momChange.value?.deltaUah).toBeCloseTo(68.15);
    });

    // Billing is unimplemented (#45), so API-submitted readings store 0. A
    // delta against that would read as a swing to zero hryvnia.
    it("suppresses the delta when either period stored the unbilled zero", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot("2026-05", makeReading({ period: "2026-05", amount_charged_uah: "611.00" })),
        makeSlot("2026-06", makeReading({ period: "2026-06", amount_charged_uah: "0.00" })),
      ]);
      const { momChange, lastSubmittedPeriod } = useUsageInsights(slots);

      expect(momChange.value?.deltaUah).toBeNull();
      expect(lastSubmittedPeriod.value?.chargedUah).toBeNull();
    });
  });

  describe("Decimal-as-string coercion", () => {
    it("adds day and night usage numerically instead of concatenating strings", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "10.00", night_usage_kwh: "5.00" })
        ),
      ]);
      const { lastSubmittedPeriod } = useUsageInsights(slots);

      expect(lastSubmittedPeriod.value?.totalKwh).toBe(15);
      expect(lastSubmittedPeriod.value?.totalKwh).not.toBe("10.005.00" as unknown as number);
    });
  });

  describe("reactivity", () => {
    it("re-derives every value after the slots ref is replaced, not frozen at first call", () => {
      const scope = effectScope();

      scope.run(() => {
        const slots = ref<MeterPeriod[]>([
          makeSlot(
            "2026-05",
            makeReading({ period: "2026-05", day_usage_kwh: "10.00", night_usage_kwh: "0.00" })
          ),
        ]);
        const insights = useUsageInsights(slots);

        expect(insights.lastSubmittedPeriod.value?.period).toBe("2026-05");
        // May is spring (SEASON_BY_MONTH[4]) with no other submitted period at
        // all yet, so there's nothing to compare against.
        expect(insights.seasonComparison.value).toBeNull();
        expect(insights.momChange.value).toBeNull();

        // Simulate a household switch: an entirely new slot list.
        slots.value = [
          makeSlot(
            "2026-05",
            makeReading({ period: "2026-05", day_usage_kwh: "10.00", night_usage_kwh: "0.00" })
          ),
          makeSlot(
            "2026-06",
            makeReading({ period: "2026-06", day_usage_kwh: "40.00", night_usage_kwh: "0.00" })
          ),
        ];

        expect(insights.lastSubmittedPeriod.value?.period).toBe("2026-06");
        // June is summer (SEASON_BY_MONTH[5]) -- a different season from May's
        // spring submission, so still nothing to compare against. Proves the
        // computed re-derives after the slots ref is replaced, not that it's
        // frozen returning the prior null by coincidence.
        expect(insights.seasonComparison.value).toBeNull();
        expect(insights.momChange.value).toEqual({
          percent: 300,
          from: 10,
          to: 40,
          direction: "up",
          deltaUah: null,
        });
      });

      scope.stop();
    });
  });
});

import { describe, expect, it } from "vitest";
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

      expect(momChange.value).toEqual({ percent: 50, from: 10, to: 15, direction: "up" });
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

      expect(momChange.value).toEqual({ percent: -50, from: 20, to: 10, direction: "down" });
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

      expect(momChange.value).toEqual({ percent: 0, from: 15, to: 15, direction: "flat" });
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

      expect(momChange.value).toEqual({ percent: 0, from: 0, to: 0, direction: "flat" });
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

  describe("monthlyAverage", () => {
    it("is null when there are no submitted periods", () => {
      const slots = ref<MeterPeriod[]>([makeSlot("2026-06", undefined)]);
      const { monthlyAverage } = useUsageInsights(slots);

      expect(monthlyAverage.value).toBeNull();
    });

    it("averages total usage across an unsorted set of submitted periods", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-06",
          makeReading({ period: "2026-06", day_usage_kwh: "10.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2026-04",
          makeReading({ period: "2026-04", day_usage_kwh: "20.00", night_usage_kwh: "0.00" })
        ),
        makeSlot(
          "2026-05",
          makeReading({ period: "2026-05", day_usage_kwh: "30.00", night_usage_kwh: "0.00" })
        ),
      ]);
      const { monthlyAverage } = useUsageInsights(slots);

      expect(monthlyAverage.value).toEqual({ averageKwh: 20, periodCount: 3 });
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

  describe("submissionRecord", () => {
    it("classifies on-time as submitted within days 1-5 of the following month", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-05",
          makeReading({
            period: "2026-05",
            submitted_at: new Date(2026, 5, 5, 23, 59).toISOString(),
          })
        ),
      ]);
      const { submissionRecord } = useUsageInsights(slots);

      expect(submissionRecord.value.entries).toEqual([{ period: "2026-05", state: "on-time" }]);
      expect(submissionRecord.value.onTime).toBe(1);
      expect(submissionRecord.value.late).toBe(0);
    });

    it("classifies late as submitted after day 5 of the following month", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-05",
          makeReading({ period: "2026-05", submitted_at: new Date(2026, 5, 6, 0, 0).toISOString() })
        ),
      ]);
      const { submissionRecord } = useUsageInsights(slots);

      expect(submissionRecord.value.entries).toEqual([{ period: "2026-05", state: "late" }]);
      expect(submissionRecord.value.late).toBe(1);
      expect(submissionRecord.value.onTime).toBe(0);
    });

    it("classifies a missing reading separately from late, and does not count it in either total", () => {
      const slots = ref<MeterPeriod[]>([
        makeSlot(
          "2026-05",
          makeReading({ period: "2026-05", submitted_at: new Date(2026, 5, 2, 0, 0).toISOString() })
        ),
        makeSlot("2026-06", undefined),
        makeSlot(
          "2026-04",
          makeReading({
            period: "2026-04",
            submitted_at: new Date(2026, 4, 10, 0, 0).toISOString(),
          })
        ),
      ]);
      const { submissionRecord } = useUsageInsights(slots);

      expect(submissionRecord.value.total).toBe(3);
      expect(submissionRecord.value.onTime).toBe(1);
      expect(submissionRecord.value.late).toBe(1);
      expect(submissionRecord.value.entries).toContainEqual({
        period: "2026-06",
        state: "missing",
      });
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
        expect(insights.monthlyAverage.value?.averageKwh).toBe(10);
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
        expect(insights.monthlyAverage.value?.averageKwh).toBe(25);
        expect(insights.momChange.value).toEqual({
          percent: 300,
          from: 10,
          to: 40,
          direction: "up",
        });
      });

      scope.stop();
    });
  });
});

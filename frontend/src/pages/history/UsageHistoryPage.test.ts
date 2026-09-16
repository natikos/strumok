import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
import { appPlugins } from "@/shared/testing/mount";
import type { MeterReadingOut } from "@shared/api/meter-readings";

import UsageHistoryPage from "./UsageHistoryPage.vue";

const { listMyMeterReadings } = vi.hoisted(() => ({
  listMyMeterReadings: vi.fn(),
}));

vi.mock("@shared/api/meter-readings", () => ({
  listMyMeterReadings,
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
    submitted_at: "2026-07-02T09:00:00.000Z",
    ...overrides,
  };
}

/**
 * Mount the page the way the router actually does, stubbing the `Button`
 * component's `as="router-link"` usage since there's no real router in this
 * unit test.
 */
async function mountPage() {
  const wrapper = mount(UsageHistoryPage, {
    global: {
      plugins: appPlugins(),
      stubs: { Button: true },
    },
  });
  await flushPromises();
  return wrapper;
}

describe("UsageHistoryPage submissionRecord", () => {
  beforeEach(() => {
    listMyMeterReadings.mockReset();
    useCurrentHousehold().setHouseholds([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("classifies a reading submitted within days 1-5 of the following month as on-time", async () => {
    listMyMeterReadings.mockResolvedValue([
      makeReading({ period: "2026-06", submitted_at: "2026-07-05T12:00:00.000Z" }),
    ]);

    const wrapper = await mountPage();
    const record = (
      wrapper.vm as unknown as {
        submissionRecord: { onTime: number; late: number; total: number };
      }
    ).submissionRecord;

    expect(record).toMatchObject({
      onTime: 1,
      late: 0,
      total: 1,
      entries: [{ period: "2026-06", state: "on-time" }],
    });
  });

  it("classifies a reading submitted after day 5 of the following month as late", async () => {
    listMyMeterReadings.mockResolvedValue([
      makeReading({ period: "2026-06", submitted_at: "2026-07-06T08:00:00.000Z" }),
    ]);

    const wrapper = await mountPage();
    const record = (
      wrapper.vm as unknown as {
        submissionRecord: { onTime: number; late: number; total: number; entries: unknown[] };
      }
    ).submissionRecord;

    expect(record.late).toBe(1);
    expect(record.onTime).toBe(0);
    expect(record.entries).toEqual([{ period: "2026-06", state: "late" }]);
  });

  it("classifies a missing reading separately from late and excludes it from the total", async () => {
    listMyMeterReadings.mockResolvedValue([
      makeReading({ id: null, period: "2026-06", submitted_at: null }),
      makeReading({ id: 2, period: "2026-07", submitted_at: "2026-08-03T10:00:00.000Z" }),
    ]);

    const wrapper = await mountPage();
    const record = (
      wrapper.vm as unknown as {
        submissionRecord: {
          onTime: number;
          late: number;
          total: number;
          entries: { period: string; state: string }[];
        };
      }
    ).submissionRecord;

    // Only the on-time July reading counts toward the ratio; June's missing
    // reading must not be scored as "late".
    expect(record.total).toBe(1);
    expect(record.onTime).toBe(1);
    expect(record.entries).toEqual([
      { period: "2026-06", state: "missing" },
      { period: "2026-07", state: "on-time" },
    ]);
  });

  it("treats a reading stamped outside its due month as late", async () => {
    // submitted_at falls months after the reading's actual due month
    // (2026-07) — there's no month it could have landed in on time.
    listMyMeterReadings.mockResolvedValue([
      makeReading({ period: "2026-06", submitted_at: "2027-01-15T12:00:00.000Z" }),
    ]);

    const wrapper = await mountPage();
    const record = (
      wrapper.vm as unknown as {
        submissionRecord: {
          onTime: number;
          late: number;
          total: number;
          entries: { state: string }[];
        };
      }
    ).submissionRecord;

    expect(record.entries).toEqual([{ period: "2026-06", state: "late" }]);
    expect(record.late).toBe(1);
    expect(record.total).toBe(1);
  });

  it("judges imported history stamped at the first of the period as on-time", async () => {
    listMyMeterReadings.mockResolvedValue([
      makeReading({ id: 1, period: "2025-01", submitted_at: "2025-02-01T00:00:00.000Z" }),
      makeReading({ id: 2, period: "2025-02", submitted_at: "2025-03-01T00:00:00.000Z" }),
      // A genuine on-time submission in its own due month.
      makeReading({ id: 3, period: "2026-06", submitted_at: "2026-07-03T09:00:00.000Z" }),
    ]);

    const wrapper = await mountPage();
    const record = (
      wrapper.vm as unknown as {
        submissionRecord: {
          onTime: number;
          late: number;
          total: number;
          entries: { period: string; state: string }[];
        };
      }
    ).submissionRecord;

    expect(record.entries).toEqual([
      { period: "2025-01", state: "on-time" },
      { period: "2025-02", state: "on-time" },
      { period: "2026-06", state: "on-time" },
    ]);
    expect(record.onTime).toBe(3);
    expect(record.total).toBe(3);
  });

  it("caps the visual strip at the most recent 12 periods while the ratio covers full history", async () => {
    // 15 consecutive periods spanning two years: 2024-10 through 2025-12.
    const periods = Array.from({ length: 15 }, (_, i) => {
      const monthIndex = 9 + i; // October (index 9) 2024 onward
      const year = 2024 + Math.floor(monthIndex / 12);
      const month = (monthIndex % 12) + 1;
      return `${year}-${String(month).padStart(2, "0")}`;
    });

    listMyMeterReadings.mockResolvedValue(
      periods.map((period, i) => {
        const [year, month] = period.split("-").map(Number);
        const dueYear = month === 12 ? year! + 1 : year;
        const dueMonth = month === 12 ? 1 : month! + 1;
        return makeReading({
          id: i + 1,
          period,
          submitted_at: `${dueYear}-${String(dueMonth).padStart(2, "0")}-01T00:00:00.000Z`,
        });
      })
    );

    const wrapper = await mountPage();
    const record = (
      wrapper.vm as unknown as {
        submissionRecord: {
          onTime: number;
          total: number;
          entries: { period: string }[];
          strip: { period: string }[];
        };
      }
    ).submissionRecord;

    expect(record.entries).toHaveLength(15);
    expect(record.total).toBe(15);
    expect(record.strip).toHaveLength(12);
    expect(record.strip[0]!.period).toBe(periods[3]);
    expect(record.strip.at(-1)!.period).toBe(periods.at(-1));
  });
});

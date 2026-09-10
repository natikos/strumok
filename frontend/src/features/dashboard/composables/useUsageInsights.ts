import { computed, type Ref } from "vue";

import type { MeterPeriod } from "@/features/dashboard/composables/useMeterReadings";
import { DEADLINE_DAY } from "@shared/utils/deadline";
import { toDecimal } from "@shared/utils/format";

/** Periods shown in the usage chart and used for the season/record aggregates. */
export const TREND_MONTHS = 12;

/** Seasons run meteorologically: Dec–Feb winter, Mar–May spring, and so on. */
export type Season = "winter" | "spring" | "summer" | "autumn";

const SEASON_BY_MONTH: Season[] = [
  "winter", // January
  "winter",
  "spring",
  "spring",
  "spring",
  "summer",
  "summer",
  "summer",
  "autumn",
  "autumn",
  "autumn",
  "winter", // December
];

export const SEASON_ORDER: Season[] = ["summer", "autumn", "winter", "spring"];

export interface PeriodUsage {
  period: string;
  monthLabel: string;
  monthLong: string;
  monthIndex: number;
  dayKwh: number;
  nightKwh: number;
  totalKwh: number;
  /** Null when the period was never billed — see the note in `toUsage`. */
  chargedUah: number | null;
}

export interface MomChange {
  percent: number;
  from: number;
  to: number;
  direction: "up" | "down" | "flat";
  /** Null unless both periods carry a real charge. */
  deltaUah: number | null;
}

export interface DaysIntoPeriod {
  day: number;
  daysInMonth: number;
  monthIndex: number;
}

export interface DayNightSplit {
  dayKwh: number;
  nightKwh: number;
  dayPct: number;
  nightPct: number;
}

export interface MonthlyAverage {
  averageKwh: number;
  periodCount: number;
}

export interface TrendSeries {
  labels: string[];
  day: (number | null)[];
  night: (number | null)[];
  presentCount: number;
}

export interface YearOverYear {
  monthIndex: number;
  monthLong: string;
  current: number;
  previous: number;
  deltaKwh: number;
  deltaPercent: number;
  direction: "up" | "down" | "flat";
  /** Null unless both years carry a real charge. */
  deltaUah: number | null;
}

export interface SeasonAverage {
  season: Season;
  averageKwh: number;
  periodCount: number;
}

export interface SubmissionRecord {
  onTime: number;
  late: number;
  total: number;
  entries: { period: string; state: "on-time" | "late" | "missing" | "unknown" }[];
}

function toUsage(slot: MeterPeriod): PeriodUsage | null {
  if (!slot.reading) {
    return null;
  }

  const dayKwh = toDecimal(slot.reading.day_usage_kwh);
  const nightKwh = toDecimal(slot.reading.night_usage_kwh);

  // Billing is unimplemented (#45): readings submitted through the API always
  // store 0, and only CSV-imported history carries a real charge. Treat 0 as
  // "not billed" so a comparison against it is suppressed rather than shown as
  // a swing to zero hryvnia.
  const charged = toDecimal(slot.reading.amount_charged_uah);

  return {
    period: slot.period,
    monthLabel: slot.monthLabel,
    monthLong: slot.monthLong,
    monthIndex: slot.date.getMonth(),
    dayKwh,
    nightKwh,
    totalKwh: dayKwh + nightKwh,
    chargedUah: charged > 0 ? charged : null,
  };
}

function percentChange(from: number, to: number): number {
  if (from === 0) {
    return to === 0 ? 0 : 100;
  }
  return ((to - from) / from) * 100;
}

/** The charge difference between two periods, or null if either wasn't billed. */
function chargeDelta(from: PeriodUsage, to: PeriodUsage): number | null {
  if (from.chargedUah === null || to.chargedUah === null) {
    return null;
  }
  return to.chargedUah - from.chargedUah;
}

function directionOf(delta: number): "up" | "down" | "flat" {
  if (delta > 0) {
    return "up";
  }
  return delta < 0 ? "down" : "flat";
}

/**
 * Derived, display-ready usage figures for the dashboard.
 *
 * Kept separate from `useMeterReadings` because these are pure functions of the
 * period list — no form state, no API, no i18n — which makes them testable from
 * plain fixtures. Every computed reads `slots.value` inside its own getter so a
 * household switch re-derives rather than freezing on the household at mount.
 *
 * Numbers stay full precision here; rounding is a render-time concern.
 */
export function useUsageInsights(slots: Ref<MeterPeriod[]>) {
  /** Oldest → newest, only periods that actually have a reading. */
  const submittedPeriods = computed<PeriodUsage[]>(() =>
    slots.value.map(toUsage).filter((usage): usage is PeriodUsage => usage !== null)
  );

  /**
   * "Last period" throughout the dashboard means the most recent *submitted*
   * period, not the currently-open one — the open period has no usage yet.
   */
  const lastSubmittedPeriod = computed<PeriodUsage | null>(
    () => submittedPeriods.value.at(-1) ?? null
  );

  const momChange = computed<MomChange | null>(() => {
    const periods = submittedPeriods.value;
    if (periods.length < 2) {
      return null;
    }

    const current = periods[periods.length - 1]!;
    const previous = periods[periods.length - 2]!;
    const to = current.totalKwh;
    const from = previous.totalKwh;

    return {
      percent: percentChange(from, to),
      from,
      to,
      direction: directionOf(to - from),
      deltaUah: chargeDelta(previous, current),
    };
  });

  const daysIntoPeriod = computed<DaysIntoPeriod>(() => {
    const now = new Date();
    return {
      day: now.getDate(),
      daysInMonth: new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate(),
      monthIndex: now.getMonth(),
    };
  });

  const dayNightSplit = computed<DayNightSplit | null>(() => {
    const last = lastSubmittedPeriod.value;
    if (!last || last.totalKwh <= 0) {
      return null;
    }

    return {
      dayKwh: last.dayKwh,
      nightKwh: last.nightKwh,
      dayPct: (last.dayKwh / last.totalKwh) * 100,
      nightPct: (last.nightKwh / last.totalKwh) * 100,
    };
  });

  const monthlyAverage = computed<MonthlyAverage | null>(() => {
    const periods = submittedPeriods.value;
    if (periods.length === 0) {
      return null;
    }

    const total = periods.reduce((sum, period) => sum + period.totalKwh, 0);
    return { averageKwh: total / periods.length, periodCount: periods.length };
  });

  /** The last 12 calendar slots, gaps included — a missing month is meaningful. */
  const recentSlots = computed<MeterPeriod[]>(() => slots.value.slice(-TREND_MONTHS));

  const trendSeries = computed<TrendSeries>(() => {
    const recent = recentSlots.value;

    return {
      labels: recent.map((slot) => slot.monthLabel),
      day: recent.map((slot) => (slot.reading ? toDecimal(slot.reading.day_usage_kwh) : null)),
      night: recent.map((slot) => (slot.reading ? toDecimal(slot.reading.night_usage_kwh) : null)),
      presentCount: recent.filter((slot) => slot.reading).length,
    };
  });

  const yearOverYear = computed<YearOverYear | null>(() => {
    const last = lastSubmittedPeriod.value;
    if (!last) {
      return null;
    }

    // Match on the "YYYY-MM" key rather than diffing Dates, which avoids the
    // month-length and DST traps in `setMonth`.
    const [year, month] = last.period.split("-");
    const previousPeriod = `${Number(year) - 1}-${month}`;
    const previousSlot = slots.value.find((slot) => slot.period === previousPeriod);
    const previous = previousSlot ? toUsage(previousSlot) : null;

    if (!previous) {
      return null;
    }

    const deltaKwh = last.totalKwh - previous.totalKwh;

    return {
      monthIndex: last.monthIndex,
      monthLong: last.monthLong,
      current: last.totalKwh,
      previous: previous.totalKwh,
      deltaKwh,
      deltaPercent: percentChange(previous.totalKwh, last.totalKwh),
      direction: directionOf(deltaKwh),
      deltaUah: chargeDelta(previous, last),
    };
  });

  const seasonAverages = computed<SeasonAverage[]>(() => {
    const totals = new Map<Season, { sum: number; count: number }>();

    for (const slot of recentSlots.value) {
      const usage = toUsage(slot);
      if (!usage) {
        continue;
      }

      const season = SEASON_BY_MONTH[usage.monthIndex]!;
      const bucket = totals.get(season) ?? { sum: 0, count: 0 };
      totals.set(season, { sum: bucket.sum + usage.totalKwh, count: bucket.count + 1 });
    }

    return SEASON_ORDER.map((season) => {
      const bucket = totals.get(season);
      return {
        season,
        averageKwh: bucket && bucket.count > 0 ? bucket.sum / bucket.count : 0,
        periodCount: bucket?.count ?? 0,
      };
    });
  });

  const submissionRecord = computed<SubmissionRecord>(() => {
    const entries = recentSlots.value.map((slot) => {
      if (!slot.reading?.submitted_at) {
        return { period: slot.period, state: "missing" as const };
      }

      // The reporting month is the one after the period: a July reading is due
      // days 1–5 of August.
      const submittedAt = new Date(slot.reading.submitted_at);
      const [year, month] = slot.period.split("-").map(Number);
      const dueMonth = new Date(year!, month!, 1);
      const inDueMonth =
        submittedAt.getFullYear() === dueMonth.getFullYear() &&
        submittedAt.getMonth() === dueMonth.getMonth();

      if (inDueMonth) {
        return {
          period: slot.period,
          state: submittedAt.getDate() <= DEADLINE_DAY ? ("on-time" as const) : ("late" as const),
        };
      }

      // Submitted before the period even closed, or long after it — the latter
      // is how bulk-imported history looks, every row stamped with the import
      // run rather than when the resident actually reported. Scoring those as
      // late would blame residents for an import artifact, so they don't count.
      return { period: slot.period, state: "unknown" as const };
    });

    const onTime = entries.filter((entry) => entry.state === "on-time").length;
    const late = entries.filter((entry) => entry.state === "late").length;

    return {
      onTime,
      late,
      // Only periods we can actually judge belong in the "x of y" ratio.
      total: onTime + late,
      entries,
    };
  });

  return {
    submittedPeriods,
    lastSubmittedPeriod,
    momChange,
    daysIntoPeriod,
    dayNightSplit,
    monthlyAverage,
    trendSeries,
    yearOverYear,
    seasonAverages,
    submissionRecord,
  };
}

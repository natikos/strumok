import { computed, type Ref } from "vue";

import type { MeterPeriod } from "@/features/dashboard/composables/useMeterReadings";
import { DEADLINE_DAY } from "@shared/utils/deadline";
import { toKwh } from "@shared/utils/format";

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
}

export interface MomChange {
  percent: number;
  from: number;
  to: number;
  direction: "up" | "down" | "flat";
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
  entries: { period: string; state: "on-time" | "late" | "missing" }[];
}

function toUsage(slot: MeterPeriod): PeriodUsage | null {
  if (!slot.reading) {
    return null;
  }

  const dayKwh = toKwh(slot.reading.day_usage_kwh);
  const nightKwh = toKwh(slot.reading.night_usage_kwh);

  return {
    period: slot.period,
    monthLabel: slot.monthLabel,
    monthLong: slot.monthLong,
    monthIndex: slot.date.getMonth(),
    dayKwh,
    nightKwh,
    totalKwh: dayKwh + nightKwh,
  };
}

function percentChange(from: number, to: number): number {
  if (from === 0) {
    return to === 0 ? 0 : 100;
  }
  return ((to - from) / from) * 100;
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

    const to = periods[periods.length - 1]!.totalKwh;
    const from = periods[periods.length - 2]!.totalKwh;
    const percent = percentChange(from, to);

    return { percent, from, to, direction: directionOf(to - from) };
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
      day: recent.map((slot) => (slot.reading ? toKwh(slot.reading.day_usage_kwh) : null)),
      night: recent.map((slot) => (slot.reading ? toKwh(slot.reading.night_usage_kwh) : null)),
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

      // On time means submitted within the day 1–5 window of the month that
      // follows the period being reported.
      const submittedAt = new Date(slot.reading.submitted_at);
      const [year, month] = slot.period.split("-").map(Number);
      const dueMonth = new Date(year!, month!, 1);
      const onTime =
        submittedAt.getFullYear() === dueMonth.getFullYear() &&
        submittedAt.getMonth() === dueMonth.getMonth() &&
        submittedAt.getDate() <= DEADLINE_DAY;

      return { period: slot.period, state: onTime ? ("on-time" as const) : ("late" as const) };
    });

    return {
      onTime: entries.filter((entry) => entry.state === "on-time").length,
      late: entries.filter((entry) => entry.state === "late").length,
      total: entries.length,
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

import { computed, type Ref } from "vue";

import type { MeterPeriod } from "@/features/dashboard/composables/useMeterReadings";
import { toDecimal } from "@shared/utils/format";

/** Periods shown in the usage chart and used for the season/record aggregates. */
export const TREND_MONTHS = 12;

/** Seasons run meteorologically: Dec–Feb winter, Mar–May spring, and so on. */
export type Season = "winter" | "spring" | "summer" | "autumn";

export const SEASON_BY_MONTH: Season[] = [
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

export interface SeasonComparison {
  season: Season;
  currentKwh: number;
  currentPeriodCount: number;
  previousYearKwh: number;
  previousPeriodCount: number;
  deltaPercent: number;
  direction: "up" | "down" | "flat";
}

export interface TrendSeries {
  labels: string[];
  fullLabels: string[];
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

  /** The last 12 calendar slots, gaps included — a missing month is meaningful. */
  const recentSlots = computed<MeterPeriod[]>(() => slots.value.slice(-TREND_MONTHS));

  const trendSeries = computed<TrendSeries>(() => {
    const recent = recentSlots.value;

    return {
      labels: recent.map((slot) => slot.monthLabel),
      fullLabels: recent.map((slot) => `${slot.monthLong} ${slot.date.getFullYear()}`),
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

  /**
   * The month indices making up a season, and the calendar year each month
   * belongs to relative to the season's own year — winter spans a year
   * boundary (Dec of the prior year, Jan/Feb of the season's year).
   */
  function seasonMonths(season: Season): { monthIndex: number; yearOffset: number }[] {
    if (season === "winter") {
      return [
        { monthIndex: 11, yearOffset: -1 }, // December
        { monthIndex: 0, yearOffset: 0 }, // January
        { monthIndex: 1, yearOffset: 0 }, // February
      ];
    }

    return SEASON_BY_MONTH.reduce<{ monthIndex: number; yearOffset: number }[]>(
      (acc, s, monthIndex) => (s === season ? [...acc, { monthIndex, yearOffset: 0 }] : acc),
      []
    );
  }

  /** Sums whatever readings exist for a season occurrence anchored on `seasonYear`. */
  function sumSeason(
    season: Season,
    seasonYear: number
  ): { totalKwh: number; periodCount: number } {
    let totalKwh = 0;
    let periodCount = 0;

    for (const { monthIndex, yearOffset } of seasonMonths(season)) {
      const period = `${seasonYear + yearOffset}-${String(monthIndex + 1).padStart(2, "0")}`;
      const slot = slots.value.find((s) => s.period === period);
      const usage = slot ? toUsage(slot) : null;
      if (usage) {
        totalKwh += usage.totalKwh;
        periodCount += 1;
      }
    }

    return { totalKwh, periodCount };
  }

  /**
   * How this season so far compares to the same season one year earlier —
   * e.g. this autumn vs. last autumn — anchored on today's actual season
   * rather than the last submitted period, so a resident behind on
   * submissions sees "no autumn reading yet" instead of a stale month
   * dressed up as current (#78).
   */
  const seasonComparison = computed<SeasonComparison | null>(() => {
    const now = new Date();
    const currentSeason = SEASON_BY_MONTH[now.getMonth()]!;
    // Winter's "season year" is anchored on its ending February, so December
    // still counts toward the winter that finishes the following year.
    const seasonYear =
      currentSeason === "winter" && now.getMonth() === 11
        ? now.getFullYear() + 1
        : now.getFullYear();

    const current = sumSeason(currentSeason, seasonYear);
    if (current.periodCount === 0) {
      return null;
    }

    const previous = sumSeason(currentSeason, seasonYear - 1);
    if (previous.periodCount === 0) {
      return null;
    }

    return {
      season: currentSeason,
      currentKwh: current.totalKwh,
      currentPeriodCount: current.periodCount,
      previousYearKwh: previous.totalKwh,
      previousPeriodCount: previous.periodCount,
      deltaPercent: percentChange(previous.totalKwh, current.totalKwh),
      direction: directionOf(current.totalKwh - previous.totalKwh),
    };
  });

  return {
    submittedPeriods,
    lastSubmittedPeriod,
    momChange,
    daysIntoPeriod,
    dayNightSplit,
    trendSeries,
    yearOverYear,
    seasonAverages,
    seasonComparison,
  };
}

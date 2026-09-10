<template>
  <div class="stat-tiles">
    <template v-if="isLoading">
      <Skeleton v-for="n in 3" :key="n" height="4.75rem" class="stat-tiles__skeleton" />
    </template>

    <template v-else>
      <div
        v-for="tile in tiles"
        :key="tile.key"
        class="stat-tile"
        :class="{ 'stat-tile--empty': tile.isEmpty }"
      >
        <span class="stat-tile__label">{{ tile.label }}</span>

        <span class="stat-tile__value" :class="tile.valueClass">
          <i v-if="tile.icon" :class="tile.icon" aria-hidden="true"></i>
          <template v-if="tile.isEmpty">—</template>
          <template v-else>
            {{ tile.value }}
            <span v-if="tile.unit" class="stat-tile__unit">{{ tile.unit }}</span>
          </template>
        </span>

        <span class="stat-tile__sub">{{ tile.sub }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type {
    DaysIntoPeriod,
    MomChange,
    MonthlyAverage,
    PeriodUsage,
  } from "@/features/dashboard/composables/useUsageInsights";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { formatMeterValue, formatUah } from "@shared/utils/format";

  interface Props {
    lastPeriod: PeriodUsage | null;
    momChange: MomChange | null;
    daysIntoPeriod: DaysIntoPeriod;
    monthlyAverage: MonthlyAverage | null;
    /** Overdue swaps the month-over-month tile for a missed-period count. */
    missedPeriods?: number;
    isLoading?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    missedPeriods: 0,
    isLoading: false,
  });

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  interface Tile {
    key: string;
    label: string;
    value: string;
    unit: string;
    sub: string;
    isEmpty: boolean;
    icon?: string;
    valueClass?: string;
  }

  const kwh = computed(() => t("units.kwh"));

  function num(value: number): string {
    return formatMeterValue(value, intlLocale.value);
  }

  function monthName(index: number): string {
    return t(`months.long.${index}`);
  }

  const lastPeriodTile = computed<Tile>(() => {
    const last = props.lastPeriod;
    if (!last) {
      return {
        key: "last",
        label: t("dashboard.lastPeriodEmpty"),
        value: "",
        unit: "",
        sub: t("dashboard.unlockAfterSecond"),
        isEmpty: true,
      };
    }

    return {
      key: "last",
      label: t("dashboard.lastPeriodEmpty"),
      value: num(last.totalKwh),
      unit: kwh.value,
      sub: `${t("meterReadings.day")} ${num(last.dayKwh)} · ${t("meterReadings.night")} ${num(last.nightKwh)} ${kwh.value}`,
      isEmpty: false,
    };
  });

  const comparisonTile = computed<Tile>(() => {
    // Overdue: the more useful number is how many periods were missed.
    if (props.missedPeriods > 0) {
      return {
        key: "missed",
        label: t("dashboard.missedPeriods"),
        value: String(props.missedPeriods),
        unit: "",
        sub: t("dashboard.awaitingReading", { month: monthName(props.daysIntoPeriod.monthIndex) }),
        isEmpty: false,
        valueClass: "stat-tile__value--missed",
      };
    }

    const mom = props.momChange;
    if (!mom) {
      return {
        key: "mom",
        label: t("dashboard.vsPrevious"),
        value: "",
        unit: "",
        sub: t("dashboard.unlockNeedsTwo"),
        isEmpty: true,
      };
    }

    const previousMonth = props.lastPeriod
      ? monthName((props.lastPeriod.monthIndex + 11) % 12)
      : "";

    // The hryvnia delta only exists for billed periods (#45), so the tile falls
    // back to the kWh movement alone rather than implying a zero-cost change.
    const sub =
      mom.deltaUah == null || mom.deltaUah === 0
        ? `${num(mom.from)} → ${num(mom.to)} ${kwh.value}`
        : t(mom.deltaUah < 0 ? "dashboard.uahLess" : "dashboard.uahMore", {
            value: formatUah(Math.abs(mom.deltaUah), intlLocale.value),
          });

    return {
      key: "mom",
      label: t("dashboard.vsMonth", { month: previousMonth }),
      value: `${Math.abs(mom.percent).toFixed(1)}%`,
      unit: "",
      sub,
      isEmpty: false,
      icon: mom.direction === "down" ? "pi pi-arrow-down" : "pi pi-arrow-up",
      valueClass: mom.direction === "down" ? "stat-tile__value--down" : "stat-tile__value--up",
    };
  });

  const averageTile = computed<Tile>(() => {
    const average = props.monthlyAverage;
    if (!average) {
      return {
        key: "avg",
        label: t("dashboard.monthlyAverage"),
        value: "",
        unit: "",
        sub: t("dashboard.unlockNeedsTwo"),
        isEmpty: true,
      };
    }

    // Below six periods the mean is too noisy to present as a plain average.
    const sub =
      average.periodCount < 6
        ? t("dashboard.onlyMonthsSoFar", { count: average.periodCount })
        : t("dashboard.monthsOfData", { count: average.periodCount });

    return {
      key: "avg",
      label: t("dashboard.monthlyAverage"),
      value: num(average.averageKwh),
      unit: kwh.value,
      sub,
      isEmpty: false,
    };
  });

  const tiles = computed<Tile[]>(() => [
    lastPeriodTile.value,
    comparisonTile.value,
    averageTile.value,
  ]);
</script>

<style scoped lang="scss">
  .stat-tiles {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-app-space-2);
    align-items: stretch;

    @include layout.respond-to("lg") {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .stat-tiles__skeleton {
    border-radius: var(--s-app-radius-md);
  }

  .stat-tile {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    // Grid children holding text need this or long labels force overflow at 360px.
    min-width: 0;
    padding: var(--s-app-space-3);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    background: var(--s-content-background);

    &--empty {
      border-style: dashed;

      .stat-tile__value {
        color: color-mix(in srgb, var(--s-content-color), transparent 65%);
      }
    }

    &__label {
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--s-content-secondary-color);
      min-width: 0;
    }

    &__value {
      display: flex;
      align-items: baseline;
      gap: 0.25em;
      font-size: 1.35rem;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
      line-height: 1.2;
      color: var(--s-content-color);
      min-width: 0;

      .pi {
        font-size: 0.7em;
        flex-shrink: 0;
      }

      &--up {
        color: var(--s-amber-800);
      }

      &--down {
        color: var(--s-green-800);
      }

      &--missed {
        color: var(--s-red-700);
      }
    }

    &__unit {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--s-content-secondary-color);
    }

    &__sub {
      font-size: 0.72rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
      min-width: 0;
    }
  }
</style>

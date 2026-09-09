<template>
  <section class="card usage-chart">
    <header class="usage-chart__header">
      <h2 class="usage-chart__title">{{ t("dashboard.recentUsage") }}</h2>

      <ul class="usage-chart__legend">
        <li class="usage-chart__legend-item">
          <span class="usage-chart__swatch usage-chart__swatch--day" aria-hidden="true"></span>
          {{ t("meterReadings.day") }}
        </li>
        <li class="usage-chart__legend-item">
          <span class="usage-chart__swatch usage-chart__swatch--night" aria-hidden="true"></span>
          {{ t("meterReadings.night") }}
        </li>
      </ul>
    </header>

    <Skeleton v-if="isLoading" height="180px" class="usage-chart__skeleton" />

    <div v-else class="usage-chart__canvas-wrap">
      <Chart
        type="bar"
        :data="chartData"
        :options="chartOptions"
        class="usage-chart__canvas"
        :canvas-props="{ 'aria-label': chartAriaLabel, role: 'img' }"
      />
    </div>

    <p v-if="isSparse" class="usage-chart__note">
      <i class="pi pi-info-circle" aria-hidden="true"></i>
      {{ t("dashboard.trendSparseNote") }}
    </p>

    <p class="usage-chart__footnote">
      {{ t("dashboard.usageChartFootnote", { count: series.labels.length }) }}
    </p>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type { TrendSeries } from "@/features/dashboard/composables/useUsageInsights";
  import { useIsDesktop } from "@shared/composables/useMediaQuery";

  /** Below this many readings the chart can't show a seasonal pattern yet. */
  const SPARSE_THRESHOLD = 6;

  interface Props {
    series: TrendSeries;
    isLoading?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), { isLoading: false });

  const { t } = useI18n();
  const isDesktop = useIsDesktop();

  const isSparse = computed(
    () => props.series.presentCount > 0 && props.series.presentCount < SPARSE_THRESHOLD
  );

  const chartAriaLabel = computed(() =>
    t("dashboard.chartAriaLabel", { count: props.series.labels.length })
  );

  function cssVar(name: string, fallback: string): string {
    if (typeof window === "undefined") {
      return fallback;
    }
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value === "" ? fallback : value;
  }

  const chartData = computed(() => {
    const day = cssVar("--s-amber-500", "#f59e0b");
    const night = cssVar("--s-primary-900", "#0e3559");

    const dataset = {
      borderRadius: 3,
      borderSkipped: false,
      barPercentage: 0.7,
      categoryPercentage: 0.78,
    };

    return {
      labels: props.series.labels,
      datasets: [
        {
          label: t("meterReadings.day"),
          data: props.series.day,
          backgroundColor: day,
          ...dataset,
        },
        {
          label: t("meterReadings.night"),
          data: props.series.night,
          backgroundColor: night,
          ...dataset,
        },
      ],
    };
  });

  const chartOptions = computed(() => {
    const grid = cssVar("--s-content-border-color", "#e2e8f0");
    const tick = cssVar("--s-content-secondary-color", "#475569");
    const tooltipBg = cssVar("--s-surface-900", "#0f172a");
    const unit = t("units.kwh");
    const labels = props.series.labels;

    return {
      responsive: true,
      maintainAspectRatio: false,
      // A missing month is meaningful, so nulls stay gaps rather than zeroes.
      spanGaps: false,
      interaction: { mode: "index" as const, intersect: false },
      font: { family: "FixelText", size: 11 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: tooltipBg,
          padding: 10,
          cornerRadius: 8,
          boxWidth: 8,
          boxHeight: 8,
          usePointStyle: true,
          callbacks: {
            label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
              ` ${ctx.dataset.label}: ${ctx.parsed.y ?? 0} ${unit}`,
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          grid: { display: false },
          border: { color: grid },
          ticks: {
            color: tick,
            font: { family: "FixelText", size: 11 },
            // All 12 periods always get a tick; at 360px there is only room for
            // an initial, so shorten rather than drop or rotate labels.
            autoSkip: false,
            maxRotation: 0,
            callback: (_value: unknown, index: number) => {
              const label = labels[index] ?? "";
              return isDesktop.value ? label : label.slice(0, 1);
            },
          },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          grid: { color: grid, drawTicks: false },
          border: { display: false },
          ticks: {
            color: tick,
            font: { family: "FixelText", size: 11 },
            maxTicksLimit: 4,
            padding: 6,
          },
        },
      },
    };
  });
</script>

<style scoped lang="scss">
  .usage-chart {
    &__header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--s-app-space-2);
      flex-wrap: wrap;
    }

    &__title {
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
      color: var(--s-content-color);
    }

    &__legend {
      display: flex;
      align-items: center;
      gap: var(--s-app-space-3);
      list-style: none;
      margin: 0;
      padding: 0;
    }

    &__legend-item {
      display: inline-flex;
      align-items: center;
      gap: var(--s-app-space-1);
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--s-content-secondary-color);
    }

    &__swatch {
      width: 0.6rem;
      height: 0.6rem;
      border-radius: 0.2rem;
      flex-shrink: 0;

      &--day {
        background: var(--s-amber-500);
      }

      &--night {
        background: var(--s-primary-900);
      }
    }

    // The canvas needs a sized, positioned parent: with maintainAspectRatio
    // false it would otherwise ratchet its own height on every resize.
    &__canvas-wrap {
      position: relative;
      height: 180px;
      width: 100%;

      @include layout.respond-to("lg") {
        height: 260px;
      }
    }

    &__canvas {
      width: 100%;
      height: 100%;
    }

    &__skeleton {
      border-radius: var(--s-app-radius-sm);
    }

    &__note {
      display: flex;
      align-items: flex-start;
      gap: var(--s-app-space-2);
      margin: 0;
      padding: var(--s-app-space-2);
      border-radius: var(--s-app-radius-sm);
      background: color-mix(in srgb, var(--s-content-color), transparent 94%);
      font-size: 0.75rem;
      color: var(--s-content-secondary-color);

      .pi {
        font-size: 0.85rem;
        flex-shrink: 0;
        margin-top: 0.1em;
      }
    }

    &__footnote {
      margin: auto 0 0;
      font-size: 0.72rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    }
  }
</style>

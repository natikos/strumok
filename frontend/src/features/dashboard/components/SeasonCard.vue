<template>
  <section class="card season-card">
    <h2 class="season-card__title">{{ t("dashboard.seasonTitle") }}</h2>

    <div class="season-card__rows">
      <div
        v-for="row in rows"
        :key="row.season"
        class="season-card__row"
        role="img"
        :aria-label="`${row.name}: ${row.formatted}`"
      >
        <span class="season-card__name">{{ row.name }}</span>
        <span class="season-card__track">
          <span class="season-card__fill" :style="{ width: `${row.widthPct}%` }"></span>
        </span>
        <span class="season-card__value">{{ row.formatted }}</span>
      </div>
    </div>

    <p class="season-card__footnote">{{ t("dashboard.seasonFootnote") }}</p>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type { SeasonAverage } from "@/features/dashboard/composables/useUsageInsights";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { formatKwh } from "@shared/utils/format";

  interface Props {
    seasons: SeasonAverage[];
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  const SEASON_LABEL_KEY: Record<string, string> = {
    summer: "dashboard.seasonSummer",
    autumn: "dashboard.seasonAutumn",
    winter: "dashboard.seasonWinter",
    spring: "dashboard.seasonSpring",
  };

  const rows = computed(() => {
    const max = Math.max(...props.seasons.map((season) => season.averageKwh), 0);

    return props.seasons.map((season) => ({
      season: season.season,
      name: t(SEASON_LABEL_KEY[season.season] ?? season.season),
      widthPct: max > 0 ? (season.averageKwh / max) * 100 : 0,
      formatted:
        season.periodCount > 0
          ? formatKwh(season.averageKwh, intlLocale.value, t("units.kwh"))
          : "—",
    }));
  });
</script>

<style scoped lang="scss">
  .season-card {
    &__title {
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
      color: var(--s-content-color);
    }

    &__rows {
      @include layout.stack(var(--s-app-space-2));
    }

    &__row {
      display: grid;
      // As in the YoY card: let the value column take the width its content
      // needs rather than clipping a 5-digit average at 360px.
      grid-template-columns: 4rem minmax(0, 1fr) auto;
      align-items: center;
      gap: var(--s-app-space-2);
    }

    &__name {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--s-content-color);
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &__track {
      height: 10px;
      border-radius: 999px;
      background: color-mix(in srgb, var(--s-content-color), transparent 94%);
      overflow: hidden;
      min-width: 0;
    }

    &__fill {
      display: block;
      height: 100%;
      border-radius: 999px;
      background: var(--s-primary-color);
    }

    &__value {
      font-size: 0.85rem;
      font-variant-numeric: tabular-nums;
      text-align: right;
      white-space: nowrap;
      color: var(--s-content-color);
    }

    &__footnote {
      margin: auto 0 0;
      font-size: 0.72rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    }
  }
</style>

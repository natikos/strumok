<template>
  <section class="card yoy-card" :class="{ 'yoy-card--unavailable': !isLoading && !comparison }">
    <header class="yoy-card__header">
      <h2 class="yoy-card__title">{{ t("dashboard.yoyTitle") }}</h2>
      <span v-if="comparison" class="yoy-card__month">{{ comparison.monthLong }}</span>
    </header>

    <template v-if="isLoading">
      <Skeleton height="12px" class="yoy-card__skeleton" />
      <Skeleton height="12px" class="yoy-card__skeleton" />
    </template>

    <template v-else-if="comparison">
      <div class="yoy-card__rows">
        <div
          v-for="row in rows"
          :key="row.year"
          class="yoy-card__row"
          role="img"
          :aria-label="t('dashboard.yoyAriaLabel', { year: row.year, value: row.formatted })"
        >
          <span class="yoy-card__year" :class="{ 'yoy-card__year--current': row.isCurrent }">
            {{ row.year }}
          </span>
          <span class="yoy-card__track">
            <span
              class="yoy-card__fill"
              :class="{ 'yoy-card__fill--current': row.isCurrent }"
              :style="{ width: `${row.widthPct}%` }"
            ></span>
          </span>
          <span class="yoy-card__value">{{ row.formatted }}</span>
        </div>
      </div>

      <footer class="yoy-card__footer">
        <span class="yoy-card__pill" :class="`yoy-card__pill--${comparison.direction}`">
          <i :class="deltaIcon" aria-hidden="true"></i>
          {{ formatKwh(Math.abs(comparison.deltaKwh), intlLocale, t("units.kwh")) }}
        </span>
        <span class="yoy-card__delta-text">{{ deltaText }}</span>
      </footer>
    </template>

    <div v-else class="yoy-card__empty">
      <i class="pi pi-calendar" aria-hidden="true"></i>
      <p class="yoy-card__empty-text">
        {{ t("dashboard.yoyUnavailable", { month: emptyMonth, year: emptyYear }) }}
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type { YearOverYear } from "@/features/dashboard/composables/useUsageInsights";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { formatKwh } from "@shared/utils/format";

  interface Props {
    comparison: YearOverYear | null;
    /** Month/year the comparison would have covered, for the unavailable copy. */
    emptyMonth: string;
    emptyYear: number;
    isLoading?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), { isLoading: false });

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  const currentYear = computed(() => new Date().getFullYear());

  const rows = computed(() => {
    const data = props.comparison;
    if (!data) {
      return [];
    }

    const max = Math.max(data.current, data.previous);
    const widthOf = (value: number) => (max > 0 ? (value / max) * 100 : 0);

    return [
      {
        year: currentYear.value,
        isCurrent: true,
        widthPct: widthOf(data.current),
        formatted: formatKwh(data.current, intlLocale.value, t("units.kwh")),
      },
      {
        year: currentYear.value - 1,
        isCurrent: false,
        widthPct: widthOf(data.previous),
        formatted: formatKwh(data.previous, intlLocale.value, t("units.kwh")),
      },
    ];
  });

  const deltaIcon = computed(() =>
    props.comparison?.direction === "down" ? "pi pi-arrow-down" : "pi pi-arrow-up"
  );

  const deltaText = computed(() => {
    const data = props.comparison;
    if (!data) {
      return "";
    }

    const value = formatKwh(Math.abs(data.deltaKwh), intlLocale.value, t("units.kwh"));
    const key = data.direction === "down" ? "dashboard.yoyLess" : "dashboard.yoyMore";
    return t(key, { value, month: data.monthLong });
  });
</script>

<style scoped lang="scss">
  .yoy-card {
    &--unavailable {
      border-style: dashed;
    }

    &__header {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: var(--s-app-space-2);
    }

    &__title {
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
      color: var(--s-content-color);
    }

    &__month {
      font-size: 0.78rem;
      font-weight: 600;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    }

    &__rows {
      @include layout.stack(var(--s-app-space-2));
    }

    &__row {
      display: grid;
      // The value column sizes to its content: a 5-digit total plus the unit
      // (longer in ua — "кВт·год") overflows a fixed 4.5rem at 360px.
      grid-template-columns: 2.5rem minmax(0, 1fr) auto;
      align-items: center;
      gap: var(--s-app-space-2);
    }

    &__year {
      font-size: 0.8rem;
      font-weight: 600;
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      font-variant-numeric: tabular-nums;

      &--current {
        font-weight: 700;
        color: var(--s-content-color);
      }
    }

    &__track {
      height: 12px;
      border-radius: 999px;
      background: color-mix(in srgb, var(--s-content-color), transparent 94%);
      overflow: hidden;
      min-width: 0;
    }

    &__fill {
      display: block;
      height: 100%;
      border-radius: 999px;
      background: var(--s-surface-300);

      &--current {
        background: var(--s-primary-color);
      }
    }

    &__value {
      font-size: 0.9rem;
      font-variant-numeric: tabular-nums;
      text-align: right;
      white-space: nowrap;
      color: var(--s-content-color);
    }

    &__footer {
      display: flex;
      align-items: center;
      gap: var(--s-app-space-2);
      flex-wrap: wrap;
      margin-top: auto;
      padding-top: var(--s-app-space-3);
      border-top: 1px solid var(--s-content-border-color);
    }

    &__pill {
      display: inline-flex;
      align-items: center;
      gap: 0.35em;
      padding: 0.25em 0.7em;
      border-radius: 2rem;
      font-size: 0.85rem;
      font-weight: 700;
      white-space: nowrap;

      .pi {
        font-size: 0.8em;
      }

      &--down {
        background: color-mix(in srgb, var(--s-green-500), transparent 88%);
        color: var(--s-green-800);
      }

      &--up,
      &--flat {
        background: color-mix(in srgb, var(--s-amber-500), transparent 88%);
        color: var(--s-amber-800);
      }
    }

    &__delta-text {
      font-size: 0.8rem;
      color: var(--s-content-secondary-color);
      min-width: 0;
    }

    &__empty {
      display: flex;
      align-items: flex-start;
      gap: var(--s-app-space-2);

      .pi {
        font-size: 1.1rem;
        flex-shrink: 0;
        color: color-mix(in srgb, var(--s-content-color), transparent 65%);
      }
    }

    &__empty-text {
      margin: 0;
      font-size: 0.8rem;
      color: var(--s-content-secondary-color);
    }
  }
</style>

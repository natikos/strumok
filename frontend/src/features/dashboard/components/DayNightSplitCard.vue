<template>
  <section class="card split-card">
    <h2 class="split-card__title">{{ t("dashboard.splitTitle") }}</h2>

    <template v-if="isLoading">
      <Skeleton height="14px" class="split-card__skeleton" />
      <Skeleton height="2.5rem" class="split-card__skeleton" />
    </template>

    <template v-else-if="split">
      <div class="split-card__bar" role="img" :aria-label="barAriaLabel">
        <span class="split-card__segment split-card__segment--day" :style="daySegmentStyle"></span>
        <span
          class="split-card__segment split-card__segment--night"
          :style="nightSegmentStyle"
        ></span>
      </div>

      <div class="split-card__rows">
        <div v-for="row in rows" :key="row.key" class="split-card__row">
          <i :class="row.icon" class="split-card__icon" :data-part="row.key" aria-hidden="true"></i>
          <span class="split-card__name">{{ row.name }}</span>
          <span class="split-card__value">{{ row.value }}</span>
          <span class="split-card__pct">{{ row.pct }}</span>
        </div>
      </div>

      <p v-if="showNightNote" class="split-card__note">{{ t("dashboard.nightCheaperNote") }}</p>
    </template>

    <p v-else class="split-card__empty">{{ t("dashboard.unlockAfterSecond") }}</p>

    <button type="button" class="split-card__link" @click="$emit('view-history')">
      {{ t("dashboard.viewFullHistory") }}
    </button>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type { DayNightSplit } from "@/features/dashboard/composables/useUsageInsights";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { formatKwh, formatMeterValue } from "@shared/utils/format";

  interface Props {
    split: DayNightSplit | null;
    /** Desktop adds the tariff hint under the rows. */
    showNightNote?: boolean;
    isLoading?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    showNightNote: false,
    isLoading: false,
  });

  defineEmits<{ "view-history": [] }>();

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  function kwhOf(value: number): string {
    return formatKwh(value, intlLocale.value, t("units.kwh"));
  }

  function pctOf(value: number): string {
    return `${formatMeterValue(Math.round(value), intlLocale.value)}%`;
  }

  // flex-grow on each segment keeps the bar proportional without percentage math.
  const daySegmentStyle = computed(() => ({ flexGrow: props.split?.dayPct ?? 0 }));
  const nightSegmentStyle = computed(() => ({ flexGrow: props.split?.nightPct ?? 0 }));

  const barAriaLabel = computed(() => {
    if (!props.split) {
      return "";
    }
    return t("dashboard.splitAriaLabel", {
      day: kwhOf(props.split.dayKwh),
      night: kwhOf(props.split.nightKwh),
    });
  });

  const rows = computed(() => {
    const split = props.split;
    if (!split) {
      return [];
    }

    return [
      {
        key: "day",
        icon: "pi pi-sun",
        name: t("meterReadings.day"),
        value: kwhOf(split.dayKwh),
        pct: pctOf(split.dayPct),
      },
      {
        key: "night",
        icon: "pi pi-moon",
        name: t("meterReadings.night"),
        value: kwhOf(split.nightKwh),
        pct: pctOf(split.nightPct),
      },
    ];
  });
</script>

<style scoped lang="scss">
  .split-card {
    &__title {
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
      color: var(--s-content-color);
    }

    &__bar {
      display: flex;
      gap: 2px;
      height: 14px;
    }

    &__segment {
      display: block;
      min-width: 0;

      &--day {
        background: var(--s-amber-500);
        border-radius: 999px 0 0 999px;
      }

      &--night {
        background: var(--s-primary-900);
        border-radius: 0 999px 999px 0;
      }
    }

    &__rows {
      @include layout.stack(var(--s-app-space-2));
    }

    &__row {
      display: flex;
      align-items: center;
      gap: var(--s-app-space-2);
    }

    &__icon {
      font-size: 0.95rem;
      flex-shrink: 0;

      &[data-part="day"] {
        color: var(--s-amber-500);
      }

      &[data-part="night"] {
        color: var(--s-primary-900);
      }
    }

    &__name {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--s-content-color);
      // Let the label ellipsis rather than crush the value column at 360px.
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &__value {
      font-size: 0.9rem;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      color: var(--s-content-color);
    }

    &__pct {
      min-width: 2.5rem;
      text-align: right;
      font-size: 0.8rem;
      font-variant-numeric: tabular-nums;
      color: var(--s-content-secondary-color);
      flex-shrink: 0;
    }

    &__note {
      margin: 0;
      font-size: 0.75rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    }

    &__empty {
      margin: 0;
      font-size: 0.8rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    }

    &__link {
      margin-top: auto;
      align-self: flex-start;
      padding: 0;
      border: none;
      background: none;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--s-primary-color);

      &:hover {
        color: var(--s-primary-hover-color);
      }
    }

    &__skeleton {
      border-radius: var(--s-app-radius-sm);
    }
  }
</style>

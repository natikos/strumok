<template>
  <div class="submitted-values">
    <div class="submitted-values__tiles">
      <div v-for="tile in tiles" :key="tile.key" class="submitted-values__tile">
        <span class="submitted-values__label">
          <component :is="tile.icon" :data-part="tile.key" aria-hidden="true" />
          {{ tile.label }}
        </span>
        <span class="submitted-values__num">{{ tile.meterValue }}</span>
        <span v-if="tile.usage" class="submitted-values__usage submission__value-usage">{{
          tile.usage
        }}</span>
      </div>
    </div>

    <p v-if="chargedThisPeriod" class="submitted-values__charge">
      <Receipt aria-hidden="true" />
      {{ t("dashboard.chargedThisPeriod") }}
      <strong class="submitted-values__charge-value">{{ chargedThisPeriod }}</strong>
    </p>
  </div>
</template>

<script setup lang="ts">
  import { Moon, Receipt, Sun } from "@primeicons/vue";
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type { PeriodUsage } from "@/features/dashboard/composables/useUsageInsights";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { formatKwh, formatMeterValue, formatUah } from "@shared/utils/format";

  interface Props {
    dayValue: number | string | null | undefined;
    nightValue: number | string | null | undefined;
    usage: PeriodUsage | null | undefined;
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  const kwh = computed(() => t("units.kwh"));

  function meter(value: number | string | null | undefined): string {
    return formatMeterValue(value, intlLocale.value);
  }

  const tiles = computed(() => [
    {
      key: "day",
      icon: Sun,
      label: t("meterReadings.day"),
      meterValue: meter(props.dayValue),
      usage: props.usage
        ? t("dashboard.usedThisPeriod", {
            value: formatKwh(props.usage.dayKwh, intlLocale.value, kwh.value),
          })
        : "",
    },
    {
      key: "night",
      icon: Moon,
      label: t("meterReadings.night"),
      meterValue: meter(props.nightValue),
      usage: props.usage
        ? t("dashboard.usedThisPeriod", {
            value: formatKwh(props.usage.nightKwh, intlLocale.value, kwh.value),
          })
        : "",
    },
  ]);

  const chargedThisPeriod = computed(() => {
    const charged = props.usage?.chargedUah;
    return charged == null ? "" : formatUah(charged, intlLocale.value);
  });
</script>

<style scoped lang="scss">
  .submitted-values {
    &__tiles {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--s-app-space-3);
    }

    &__tile {
      @include layout.stack(var(--s-app-space-1));
      min-width: 0;
      padding: var(--s-app-space-3);
      border-radius: var(--s-app-radius-md);
      background: color-mix(in srgb, var(--s-content-color), transparent 94%);
    }

    &__label {
      display: inline-flex;
      align-items: center;
      gap: var(--s-app-space-1);
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--s-content-secondary-color);

      svg[data-part="day"] {
        color: var(--s-amber-500);
      }

      svg[data-part="night"] {
        color: var(--s-primary-900);
      }
    }

    &__num {
      font-size: 1.15rem;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
      color: var(--s-content-color);
    }

    &__usage {
      font-size: 0.75rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    }

    &__charge {
      display: flex;
      align-items: center;
      gap: var(--s-app-space-2);
      margin: 0;
      margin-top: var(--s-app-space-3);
      font-size: 0.85rem;
      color: var(--s-content-secondary-color);

      svg {
        flex-shrink: 0;
        color: var(--s-primary-900);
      }
    }

    &__charge-value {
      color: var(--s-content-color);
      font-variant-numeric: tabular-nums;
    }
  }
</style>

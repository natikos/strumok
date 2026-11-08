<template>
  <div v-if="rate" class="tariff-strip">
    <p class="tariff-strip__full" role="status">
      <span class="tariff-strip__title">
        <Bolt class="tariff-strip__bolt" aria-hidden="true" />
        {{ t("tariff.title") }}
      </span>
      <span class="tariff-strip__rate tariff-strip__rate--day">
        <Sun class="tariff-strip__icon" aria-hidden="true" />
        <span class="tariff-strip__label">{{ t("tariff.day") }}</span>
        <strong class="tariff-strip__value">{{ dayLabel }}</strong>
      </span>
      <span class="tariff-strip__rate tariff-strip__rate--night">
        <Moon class="tariff-strip__icon" aria-hidden="true" />
        <span class="tariff-strip__label">{{ t("tariff.night") }}</span>
        <strong class="tariff-strip__value">{{ nightLabel }}</strong>
      </span>
      <span class="tariff-strip__from">{{ t("tariff.from", { date: fromLabel }) }}</span>
    </p>

    <button
      class="tariff-strip__compact"
      type="button"
      :aria-label="`${t('tariff.title')}: ${t('tariff.day')} ${dayLabel}, ${t('tariff.night')} ${nightLabel}`"
      @click="popover?.toggle($event)"
    >
      <Sun class="tariff-strip__icon tariff-strip__icon--day" aria-hidden="true" />
      {{ plain(rate.day_rate_uah) }}
      <Moon class="tariff-strip__icon tariff-strip__icon--night" aria-hidden="true" />
      {{ plain(rate.night_rate_uah) }}
    </button>
    <Popover ref="popover">
      <div class="tariff-strip__details">
        <strong>{{ t("tariff.title") }}</strong>
        <span>{{ t("tariff.day") }}: {{ dayLabel }}</span>
        <span>{{ t("tariff.night") }}: {{ nightLabel }}</span>
        <span>{{ t("tariff.from", { date: fromLabel }) }}</span>
      </div>
    </Popover>
  </div>
</template>

<script setup lang="ts">
  import { Bolt, Moon, Sun } from "@primeicons/vue";
  import { format, parseISO } from "date-fns";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { type CurrentRateOut, getCurrentRate } from "@shared/api/billing";
  import { formatUah, toDecimal } from "@shared/utils/format";

  const { t } = useI18n();
  const locale = navigator.language;

  const rate = ref<CurrentRateOut | null>(null);
  const popover = ref<{ toggle: (event: Event) => void } | null>(null);
  const dayLabel = computed(() =>
    rate.value ? t("tariff.perKwh", { amount: money(rate.value.day_rate_uah) }) : ""
  );
  const nightLabel = computed(() =>
    rate.value ? t("tariff.perKwh", { amount: money(rate.value.night_rate_uah) }) : ""
  );
  const fromLabel = computed(() =>
    rate.value ? format(parseISO(`${rate.value.effective_from}-01`), "dd.MM") : ""
  );

  // Bare number for the compact pill; the popover carries the currency and unit.
  function plain(value: string): string {
    return toDecimal(value).toLocaleString(locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function money(value: string): string {
    return formatUah(value, locale);
  }

  // Advisory only: with no rate, or a failed load, show nothing rather than a guess.
  onMounted(async () => {
    try {
      rate.value = await getCurrentRate();
    } catch {
      rate.value = null;
    }
  });
</script>

<style scoped lang="scss">
  .tariff-strip {
    color: color-mix(in srgb, var(--s-content-color), transparent 30%);
    font-size: 0.85rem;
    min-width: 0;

    &__full {
      align-items: center;
      display: none;
      flex-wrap: wrap;
      gap: var(--s-app-space-2) var(--s-app-space-3);
      justify-content: center;
      margin: 0;

      @include layout.respond-to("lg") {
        display: flex;
      }
    }

    &__title {
      align-items: center;
      color: var(--s-content-color);
      display: inline-flex;
      font-weight: 600;
      gap: var(--s-app-space-1);
    }

    &__bolt {
      color: var(--s-amber-500);
    }

    &__rate {
      align-items: center;
      background: var(--s-content-hover-background);
      border: 1px solid var(--s-content-border-color);
      border-radius: 999px;
      display: inline-flex;
      gap: var(--s-app-space-2);
      padding: 0.2rem var(--s-app-space-3);

      &--day .tariff-strip__icon {
        color: var(--s-amber-500);
      }

      &--night .tariff-strip__icon {
        color: var(--s-primary-400);
      }
    }

    &__icon {
      font-size: 0.9rem;

      &--day {
        color: var(--s-amber-500);
      }

      &--night {
        color: var(--s-primary-400);
      }
    }

    &__value {
      color: var(--s-content-color);
      font-variant-numeric: tabular-nums;
    }

    &__from {
      font-size: 0.8rem;
      opacity: 0.8;
    }

    &__compact {
      align-items: center;
      background: var(--s-content-hover-background);
      border: 1px solid var(--s-content-border-color);
      border-radius: 999px;
      color: var(--s-content-color);
      cursor: pointer;
      display: inline-flex;
      font: inherit;
      font-variant-numeric: tabular-nums;
      font-weight: 600;
      gap: var(--s-app-space-1);
      padding: var(--s-app-space-1) var(--s-app-space-3);
      white-space: nowrap;

      @include layout.respond-to("lg") {
        display: none;
      }
    }

    &__details {
      @include layout.stack(var(--s-app-space-1));
      font-size: 0.85rem;
    }
  }
</style>

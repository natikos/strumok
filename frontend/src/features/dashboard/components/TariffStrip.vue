<template>
  <div v-if="rate" class="tariff-strip">
    <p class="tariff-strip__full" role="status">
      <span class="tariff-strip__title">{{ t("tariff.title") }}</span>
      <span class="tariff-strip__rate">{{ t("tariff.day") }}: {{ dayLabel }}</span>
      <span class="tariff-strip__rate">{{ t("tariff.night") }}: {{ nightLabel }}</span>
      <span class="tariff-strip__from">{{ t("tariff.from", { date: fromLabel }) }}</span>
    </p>

    <button
      class="tariff-strip__compact"
      type="button"
      :aria-label="`${t('tariff.title')}: ${t('tariff.day')} ${dayLabel}, ${t('tariff.night')} ${nightLabel}`"
      @click="popover?.toggle($event)"
    >
      {{ money(rate.day_rate_uah) }}/{{ money(rate.night_rate_uah) }}
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
  import { format, parseISO } from "date-fns";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { type CurrentRateOut, getCurrentRate } from "@shared/api/billing";
  import { formatUah } from "@shared/utils/format";

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
      display: none;
      flex-wrap: wrap;
      gap: var(--s-app-space-1) var(--s-app-space-3);
      justify-content: center;
      margin: 0;

      @include layout.respond-to("lg") {
        display: flex;
      }
    }

    &__title {
      font-weight: 600;
    }

    &__compact {
      background: var(--s-content-hover-background);
      border: 0;
      border-radius: 999px;
      color: var(--s-content-color);
      cursor: pointer;
      font: inherit;
      font-weight: 600;
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

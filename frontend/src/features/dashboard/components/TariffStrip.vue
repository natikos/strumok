<template>
  <p v-if="rate" class="tariff-strip" role="status">
    <span class="tariff-strip__title">{{ t("tariff.title") }}</span>
    <span class="tariff-strip__rate">
      {{ t("tariff.day") }}: {{ t("tariff.perKwh", { amount: money(rate.day_rate_uah) }) }}
    </span>
    <span class="tariff-strip__rate">
      {{ t("tariff.night") }}: {{ t("tariff.perKwh", { amount: money(rate.night_rate_uah) }) }}
    </span>
    <span class="tariff-strip__from">{{ t("tariff.from", { date: fromLabel }) }}</span>
  </p>
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
    display: flex;
    flex-wrap: wrap;
    font-size: 0.85rem;
    gap: var(--s-app-space-1) var(--s-app-space-3);
    margin: 0;
    min-width: 0;

    &__title {
      font-weight: 600;
    }
  }
</style>

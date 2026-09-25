<template>
  <section class="card empty-usage">
    <ChartBar aria-hidden="true" />
    <h2 class="empty-usage__title">{{ t("dashboard.emptyChartTitle") }}</h2>
    <p class="empty-usage__body">{{ t("dashboard.emptyChartBody") }}</p>
  </section>
</template>

<script setup lang="ts">
  import { ChartBar } from "@primeicons/vue";
  import { useI18n } from "vue-i18n";

  const { t } = useI18n();
</script>

<style scoped lang="scss">
  .empty-usage {
    align-items: center;
    border-style: dashed;
    gap: var(--s-app-space-2);
    text-align: center;

    svg {
      width: 1.5rem;
      height: 1.5rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 65%);
    }

    &__title {
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
      color: var(--s-content-color);
    }

    &__body {
      margin: 0;
      max-width: 34rem;
      font-size: 0.85rem;
      line-height: 1.45;
      color: var(--s-content-secondary-color);
    }
  }
</style>

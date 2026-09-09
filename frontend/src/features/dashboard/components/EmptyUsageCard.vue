<template>
  <section class="card empty-usage">
    <i class="pi pi-chart-bar" aria-hidden="true"></i>
    <h2 class="empty-usage__title">{{ t("dashboard.emptyChartTitle") }}</h2>
    <p class="empty-usage__body">{{ t("dashboard.emptyChartBody") }}</p>
  </section>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";

  const { t } = useI18n();
</script>

<style scoped lang="scss">
  .empty-usage {
    align-items: center;
    border-style: dashed;
    gap: var(--s-app-space-2);
    text-align: center;

    .pi {
      font-size: 1.5rem;
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

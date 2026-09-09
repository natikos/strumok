<template>
  <section class="card first-run">
    <h2 class="first-run__title">{{ t("dashboard.firstRunTitle") }}</h2>

    <ol class="first-run__steps">
      <li v-for="(step, index) in steps" :key="index" class="first-run__step">
        <span class="first-run__number" aria-hidden="true">{{ index + 1 }}</span>
        <span class="first-run__text">{{ step }}</span>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  const { t } = useI18n();

  const steps = computed(() => [
    t("dashboard.firstRunStep1"),
    t("dashboard.firstRunStep2"),
    t("dashboard.firstRunStep3"),
  ]);
</script>

<style scoped lang="scss">
  .first-run {
    border-color: var(--s-primary-100);

    &__title {
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
      color: var(--s-content-color);
    }

    &__steps {
      @include layout.stack(var(--s-app-space-3));
      list-style: none;
      margin: 0;
      padding: 0;
      counter-reset: none;
    }

    &__step {
      display: flex;
      align-items: flex-start;
      gap: var(--s-app-space-3);
    }

    &__number {
      @include layout.center-square(1.5rem);
      flex-shrink: 0;
      border-radius: 999px;
      background: var(--s-primary-50);
      color: var(--s-primary-color);
      font-size: 0.78rem;
      font-weight: 700;
    }

    &__text {
      font-size: 0.85rem;
      line-height: 1.45;
      color: var(--s-content-secondary-color);
      min-width: 0;
    }
  }
</style>

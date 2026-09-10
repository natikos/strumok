<template>
  <section class="card record-card">
    <header class="record-card__header">
      <h2 class="record-card__title">{{ t("dashboard.recordTitle") }}</h2>
      <span v-if="record.total > 0" class="record-card__value">
        {{ t("dashboard.recordValue", { onTime: record.onTime, total: record.total }) }}
      </span>
    </header>

    <div class="record-card__strip" role="img" :aria-label="stripAriaLabel">
      <span
        v-for="entry in record.entries"
        :key="entry.period"
        class="record-card__segment"
        :class="`record-card__segment--${entry.state}`"
      ></span>
    </div>

    <ul class="record-card__legend">
      <li class="record-card__legend-item">
        <span class="record-card__swatch record-card__swatch--on-time" aria-hidden="true"></span>
        {{ t("dashboard.recordOnTime") }}
      </li>
      <li class="record-card__legend-item">
        <span class="record-card__swatch record-card__swatch--late" aria-hidden="true"></span>
        {{ t("dashboard.recordLate") }}
      </li>
    </ul>

    <button type="button" class="record-card__link" @click="$emit('view-history')">
      {{ t("dashboard.viewFullHistory") }}
    </button>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type { SubmissionRecord } from "@/features/dashboard/composables/useUsageInsights";

  interface Props {
    record: SubmissionRecord;
  }

  const props = defineProps<Props>();

  defineEmits<{ "view-history": [] }>();

  const { t } = useI18n();

  const stripAriaLabel = computed(() =>
    t("dashboard.recordValue", {
      onTime: props.record.onTime,
      total: props.record.total,
    })
  );
</script>

<style scoped lang="scss">
  .record-card {
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

    &__value {
      font-size: 0.9rem;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      color: var(--s-content-color);
    }

    &__strip {
      display: flex;
      gap: var(--s-app-space-1);
    }

    &__segment {
      flex: 1;
      height: 22px;
      border-radius: 3px;
      background: color-mix(in srgb, var(--s-content-color), transparent 94%);
      min-width: 0;

      &--on-time {
        background: var(--s-primary-color);
      }

      &--late {
        background: var(--s-amber-500);
      }

      // Backfilled history: submitted, but not on a timeline we can judge.
      &--unknown {
        background: color-mix(in srgb, var(--s-content-color), transparent 88%);
      }
    }

    &__legend {
      display: flex;
      align-items: center;
      gap: var(--s-app-space-3);
      list-style: none;
      margin: 0;
      padding: 0;
    }

    &__legend-item {
      display: inline-flex;
      align-items: center;
      gap: var(--s-app-space-1);
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--s-content-secondary-color);
    }

    &__swatch {
      width: 0.6rem;
      height: 0.6rem;
      border-radius: 0.2rem;
      flex-shrink: 0;

      &--on-time {
        background: var(--s-primary-color);
      }

      &--late {
        background: var(--s-amber-500);
      }
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
  }
</style>

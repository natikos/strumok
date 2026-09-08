<template>
  <div class="card deadline-card">
    <div class="deadline-card__header">
      <span class="deadline-card__icon-wrap">
        <i class="pi pi-clock" aria-hidden="true"></i>
      </span>
      <div>
        <h3 class="card__title">{{ t("deadlineCard.label") }}</h3>
        <p :class="['deadline-card__status', `deadline-card__status--${status}`]">
          {{ t(`statuses.meterReading.${toCamelCase(status)}`) }}
        </p>
      </div>
    </div>

    <div class="deadline-card__content">
      <p class="deadline-card__description">
        {{ t(`deadlineCard.nextPeriod`, { month: t(`months.long.${month}`) }) }}
      </p>
      <p class="deadline-card__days">{{ t("deadline.dueIn", { days: daysDisplay }) }}</p>
      <div class="deadline-card__progress">
        <ProgressBar
          :value="progressPercent"
          :show-value="false"
          class="deadline-card__progress-bar"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { toCamelCase } from "@utils/string";
  import { addMonths, differenceInCalendarDays, setDate, startOfToday } from "date-fns";
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import { DEADLINE_DAY, getDaysLeft, getDeadlineStatus } from "@/shared/utils/deadline";
  import type { MeterReadingOut } from "@shared/api/meter-readings";

  interface Props {
    currentReading: MeterReadingOut | null | undefined;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const month = computed(() => {
    const submissionDaysLeft = getDaysLeft();
    const currentMonth = new Date().getMonth();
    return submissionDaysLeft <= 0 ? currentMonth : currentMonth - 1;
  });

  const daysDisplay = computed(() => {
    const daysLeft = getDaysLeft();
    if (daysLeft > 0) {
      return daysLeft;
    }

    const nextMonth = addMonths(new Date(), 1);
    const nextDeadlineEnd = setDate(nextMonth, DEADLINE_DAY);
    return differenceInCalendarDays(nextDeadlineEnd, startOfToday());
  });

  const status = computed(() => getDeadlineStatus(props.currentReading?.submitted_at));

  const progressPercent = computed(() => {
    if (daysDisplay.value === 0) {
      return 100;
    }
    // Assume 30 days per billing period
    return Math.max(0, Math.min(100, ((30 - daysDisplay.value) / 30) * 100));
  });
</script>

<style scoped lang="scss">
  .deadline-card {
    display: flex;
    flex-direction: column;
    gap: var(--s-app-space-4);

    &__header {
      display: flex;
      align-items: center;
      gap: var(--s-app-space-3);
    }

    &__icon-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 2.5rem;
      height: 2.5rem;
      border-radius: var(--s-app-radius-md);
      background: color-mix(in srgb, var(--s-primary-color), transparent 88%);
      flex-shrink: 0;

      .pi {
        font-size: 1.2rem;
        color: var(--s-primary-color);
      }
    }

    &__title {
      font-size: 0.82rem;
      font-weight: 600;
      text-transform: uppercase;
      margin: 0;
    }

    &__status {
      font-size: 0.9rem;
      margin: 0.25rem 0 0;
      font-weight: 500;

      &--due {
        color: var(--s-primary-color);
      }

      &--overdue {
        color: var(--s-red-500);
      }

      &--submitted {
        color: var(--s-green-800);
      }

      &--submitted-late {
        color: var(--s-amber-800);
      }
    }

    &__content {
      @include layout.stack(var(--s-app-space-2));
    }

    &__description {
      color: var(--s-content-secondary-color);
      margin: 0;
    }

    &__days {
      font-size: 0.9rem;
      color: var(--s-content-secondary-color);
      margin: 0;
    }

    &__progress {
      width: 100%;
      min-height: 0.5rem;

      :deep(.p-progressbar) {
        height: 0.375rem;
        border-radius: 0.1875rem;
        background: color-mix(in srgb, var(--s-content-color), transparent 85%);
      }

      :deep(.p-progressbar-value) {
        background: var(--s-primary-color);
        border-radius: 0.1875rem;
        transition: width 0.3s ease;
      }
    }
  }
</style>

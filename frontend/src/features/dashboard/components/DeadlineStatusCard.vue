<template>
  <section
    class="card deadline-status"
    :class="`deadline-status--${status}`"
    :aria-labelledby="headlineId"
  >
    <div class="deadline-status__header">
      <span class="deadline-status__period">{{ periodLabel }}</span>

      <template v-if="isLoading">
        <Skeleton height="1.5rem" width="110px" class="deadline-status__skeleton-badge" />
      </template>
      <template v-else>
        <DeadlineBadge :status="status" />
      </template>
    </div>

    <template v-if="isLoading">
      <Skeleton height="1.75rem" width="80%" class="deadline-status__skeleton-headline" />
      <Skeleton height="1rem" width="60%" class="deadline-status__skeleton-subline" />
      <Skeleton height="0.375rem" width="100%" class="deadline-status__skeleton-strip" />
    </template>

    <template v-else>
      <div class="deadline-status__status" role="status" aria-live="polite">
        <h2 :id="headlineId" class="deadline-status__headline">
          <i v-if="headlineIcon" :class="headlineIcon" aria-hidden="true"></i>
          {{ headline }}
        </h2>
        <p class="deadline-status__subline">{{ subline }}</p>
      </div>

      <div
        v-if="status !== 'submitted' && status !== 'submitted-late'"
        class="deadline-status__strip"
        role="img"
        :aria-label="stripAriaLabel"
      >
        <div class="deadline-status__strip-track">
          <span
            v-for="segment in windowSegments"
            :key="segment.day"
            class="deadline-status__strip-segment"
            :class="`deadline-status__strip-segment--${segment.state}`"
          ></span>
        </div>
        <div class="deadline-status__strip-captions">
          <span
            v-for="segment in windowSegments"
            :key="segment.day"
            class="deadline-status__strip-caption"
            :class="{ 'deadline-status__strip-caption--today': segment.isToday }"
          >
            {{ segment.day }}
          </span>
        </div>
      </div>

      <template v-else>
        <div class="deadline-status__values">
          <div class="deadline-status__value-tile">
            <i class="pi pi-sun" aria-hidden="true"></i>
            <span class="deadline-status__value-label">{{ t("meterReadings.day") }}</span>
            <span class="deadline-status__value-num">{{
              formatMeterValue(dayMeterValue, intlLocale)
            }}</span>
          </div>
          <div class="deadline-status__value-tile">
            <i class="pi pi-moon" aria-hidden="true"></i>
            <span class="deadline-status__value-label">{{ t("meterReadings.night") }}</span>
            <span class="deadline-status__value-num">{{
              formatMeterValue(nightMeterValue, intlLocale)
            }}</span>
          </div>
        </div>

        <div class="deadline-status__footer">
          <p class="deadline-status__lock-note">{{ t("meterReadings.lockNote") }}</p>
          <Button
            class="deadline-status__edit-btn"
            severity="secondary"
            :outlined="true"
            :label="t('meterReadings.editSubmitted')"
            @click="$emit('edit')"
          />
        </div>
      </template>
    </template>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { DEADLINE_DAY } from "@/shared/utils/deadline";
  import type { DeadlineStatus } from "@shared/utils/deadline";
  import { formatMeterValue } from "@shared/utils/format";

  import DeadlineBadge from "./DeadlineBadge.vue";

  interface Props {
    status: DeadlineStatus;
    daysLeft: number;
    billingMonthIndex: number;
    submittedAt?: string | null | undefined;
    dayMeterValue?: number | string | null | undefined;
    nightMeterValue?: number | string | null | undefined;
    isFirstPeriod?: boolean | undefined;
    isLoading?: boolean | undefined;
  }

  const props = defineProps<Props>();
  defineEmits<{ edit: [] }>();

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  const headlineId = "deadline-status-headline";

  const periodLabel = computed(() => t(`months.long.${props.billingMonthIndex}`).toUpperCase());

  const monthName = computed(() => t(`months.long.${props.billingMonthIndex}`));

  const formattedSubmittedAt = computed(() => {
    if (!props.submittedAt) {
      return "";
    }
    return new Date(props.submittedAt).toLocaleString(intlLocale.value, {
      day: "numeric",
      month: "long",
      hour: "2-digit",
      minute: "2-digit",
    });
  });

  const headlineIcon = computed(() => {
    if (props.status === "submitted" || props.status === "submitted-late") {
      return "pi pi-check-circle";
    }
    return null;
  });

  const headline = computed(() => {
    if (props.isFirstPeriod && props.status === "due") {
      return t("deadlineStatus.firstPeriodHeadline");
    }

    switch (props.status) {
      case "due":
        return t("deadlineStatus.daysLeft", { count: props.daysLeft }, props.daysLeft);
      case "submitted":
      case "submitted-late":
        return t("deadlineStatus.submittedHeadline");
      case "overdue":
      default:
        return t("deadlineStatus.overdueHeadline");
    }
  });

  const subline = computed(() => {
    if (props.isFirstPeriod && props.status === "due") {
      return t("deadlineStatus.firstPeriodExplainer");
    }

    switch (props.status) {
      case "due":
        return t("deadlineStatus.windowClosesAt", {
          day: DEADLINE_DAY,
          month: monthName.value,
        });
      case "submitted":
        return t("deadlineStatus.submittedDetail", {
          date: formattedSubmittedAt.value,
          day: DEADLINE_DAY,
          month: monthName.value,
        });
      case "submitted-late":
        return t("deadlineStatus.submittedLateDetail");
      case "overdue":
      default:
        return t("deadlineStatus.windowClosedAt", {
          day: DEADLINE_DAY,
          month: monthName.value,
        });
    }
  });

  type SegmentState = "elapsed" | "today" | "future";

  const windowSegments = computed(() => {
    const today = new Date().getDate();
    const isOverdue = props.status === "overdue";

    return Array.from({ length: DEADLINE_DAY }, (_, index) => {
      const day = index + 1;
      let state: SegmentState = "future";
      if (isOverdue) {
        state = "elapsed";
      } else if (day < today) {
        state = "elapsed";
      } else if (day === today) {
        state = "today";
      }

      return { day, isToday: day === today && !isOverdue, state };
    });
  });

  const stripAriaLabel = computed(() => {
    const elapsed = windowSegments.value.filter((s) => s.state === "elapsed").length;
    return t("deadlineStatus.stripAriaLabel", {
      day: DEADLINE_DAY,
      elapsed,
      total: DEADLINE_DAY,
    });
  });
</script>

<style scoped lang="scss">
  .deadline-status {
    container-type: inline-size;

    &__header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--s-app-space-2);
      flex-wrap: wrap;
    }

    &__period {
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    }

    &__status {
      @include layout.stack(var(--s-app-space-1));
    }

    &__headline {
      display: flex;
      align-items: center;
      gap: var(--s-app-space-2);
      margin: 0;
      font-size: clamp(1.25rem, 1rem + 2.5cqw, 1.75rem);
      font-weight: 700;
      line-height: 1.2;
      letter-spacing: -0.01em;
      color: var(--s-content-color);

      .pi {
        font-size: 0.7em;
        flex-shrink: 0;
      }
    }

    &__subline {
      margin: 0;
      font-size: 0.9rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 25%);
    }

    &__strip {
      @include layout.stack(var(--s-app-space-1));
    }

    &__strip-track {
      display: flex;
      gap: var(--s-app-space-1);
    }

    &__strip-segment {
      flex: 1;
      height: 6px;
      border-radius: 3px;
      background: var(--s-surface-200);

      &--elapsed {
        background: var(--s-primary-color);
      }

      &--today {
        background: color-mix(in srgb, var(--s-primary-color), transparent 40%);
      }
    }

    &__strip-captions {
      display: flex;
      gap: var(--s-app-space-1);
    }

    &__strip-caption {
      flex: 1;
      text-align: center;
      font-size: 0.7rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);

      &--today {
        font-weight: 700;
        color: var(--s-content-color);
      }
    }

    &__values {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--s-app-space-3);
    }

    &__value-tile {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: var(--s-app-space-1);
      min-width: 0;
      padding: var(--s-app-space-2);
      border-radius: var(--s-app-radius-md);
      background: color-mix(in srgb, var(--s-content-color), transparent 94%);

      .pi {
        font-size: 1rem;
        color: color-mix(in srgb, var(--s-content-color), transparent 30%);
      }
    }

    &__value-label {
      font-size: 0.75rem;
      font-weight: 600;
      color: color-mix(in srgb, var(--s-content-color), transparent 30%);
    }

    &__value-num {
      font-size: 1.2rem;
      font-weight: 700;
      color: var(--s-content-color);
    }

    &__footer {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: var(--s-app-space-2);
      padding-top: var(--s-app-space-3);
      border-top: 1px solid var(--s-content-border-color);

      @include layout.respond-to("sm") {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
      }
    }

    &__lock-note {
      margin: 0;
      font-size: 0.78rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    }

    &__edit-btn {
      width: 100%;
      min-height: 3.25rem;
      flex-shrink: 0;

      @include layout.respond-to("sm") {
        width: auto;
        min-height: 0;
      }
    }

    &--overdue {
      .deadline-status__strip-segment--elapsed {
        background: var(--s-red-500);
      }
    }

    &__skeleton-badge {
      border-radius: 2rem;
    }

    &__skeleton-headline,
    &__skeleton-subline,
    &__skeleton-strip {
      border-radius: var(--s-app-radius-sm);
    }
  }
</style>

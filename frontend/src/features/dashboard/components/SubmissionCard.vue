<template>
  <div class="submission" :class="{ [`submission--${normalizedDeadline.status}`]: !isLoading }">
    <section class="submission__main" :aria-labelledby="headlineId">
      <header class="submission__header">
        <span class="submission__period">{{ periodLabel }}</span>

        <Skeleton v-if="isLoading" height="1.5rem" width="110px" class="submission__badge-skel" />
        <DeadlineBadge v-else :status="normalizedDeadline.status" />
      </header>

      <SubmissionSkeleton v-if="isLoading" />

      <template v-else>
        <div class="submission__status" role="status" aria-live="polite">
          <h2 :id="headlineId" class="submission__headline">
            <i v-if="showSubmittedView" class="pi pi-check-circle" aria-hidden="true"></i>
            {{ headline }}
          </h2>
          <p class="submission__subline">{{ subline }}</p>
        </div>

        <!-- Submitted: values replace the form until an edit is in progress. -->
        <SubmittedValues
          v-if="showSubmittedView && normalizedSubmission"
          class="submission__values"
          :day-value="normalizedSubmission.dayValue"
          :night-value="normalizedSubmission.nightValue"
          :usage="normalizedSubmission.usage"
          :can-edit="canEdit"
          @edit="$emit('edit')"
        />

        <SubmissionForm
          v-else
          class="submission__form"
          :is-late="isLate"
          :errors="normalizedForm.errors"
          :day-value="normalizedForm.dayValue"
          :night-value="normalizedForm.nightValue"
          :previous-day-value="normalizedForm.previousDayValue"
          :previous-night-value="normalizedForm.previousNightValue"
          :is-submitting="isSubmitting"
          :submit-label="submitLabel"
          @update:day-value="$emit('update:dayMeterValue', $event)"
          @update:night-value="$emit('update:nightMeterValue', $event)"
          @submit="$emit('submit')"
        />
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import { useSubmissionCopy } from "@/features/dashboard/composables/useSubmissionCopy";
  import type { PeriodUsage } from "@/features/dashboard/composables/useUsageInsights";
  import type { FieldErrors } from "@/features/dashboard/types";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { type DeadlineStatus, getDeadlineMonthIndex } from "@shared/utils/deadline";

  import DeadlineBadge from "./DeadlineBadge.vue";
  import SubmissionForm from "./SubmissionForm.vue";
  import SubmissionSkeleton from "./SubmissionSkeleton.vue";
  import SubmittedValues from "./SubmittedValues.vue";

  export interface SubmissionDeadline {
    status: DeadlineStatus;
    daysLeft: number;
    billingMonthIndex: number;
    /** Month the submit window closes in — distinct from the billing period being reported on. */
    deadlineMonthIndex: number;
  }

  /** The already-submitted reading for the current period, once one exists. */
  export interface SubmissionValues {
    submittedAt: string | null | undefined;
    dayValue: number | string | null | undefined;
    nightValue: number | string | null | undefined;
    usage: PeriodUsage | null | undefined;
  }

  export interface SubmissionFormState {
    errors: FieldErrors;
    dayValue: number | null;
    nightValue: number | null;
    previousDayValue?: number | string | null | undefined;
    previousNightValue?: number | string | null | undefined;
  }

  interface Props {
    deadline?: SubmissionDeadline | null | undefined;
    status?: DeadlineStatus | undefined;
    daysLeft?: number | undefined;
    billingMonthIndex?: number | undefined;
    deadlineMonthIndex?: number | undefined;
    isSubmitting?: boolean | undefined;
    isLoading?: boolean | undefined;
    isFirstPeriod?: boolean | undefined;
    /** Reopens the form over a submitted period, until the edit is saved. */
    isEditing?: boolean | undefined;
    /** Off until the backend supports updating a submitted reading (#57). */
    canEdit?: boolean | undefined;
    /** Present once the current period has a submitted reading. */
    submission?: SubmissionValues | null | undefined;
    submittedAt?: string | null | undefined;
    submittedDayValue?: number | string | null | undefined;
    submittedNightValue?: number | string | null | undefined;
    lastPeriod?: PeriodUsage | null | undefined;
    form?: SubmissionFormState | null | undefined;
    errors?: FieldErrors | undefined;
    dayMeterValue?: number | null | undefined;
    nightMeterValue?: number | null | undefined;
    previousDayMeterValue?: number | string | null | undefined;
    previousNightMeterValue?: number | string | null | undefined;
  }

  const props = withDefaults(defineProps<Props>(), {
    isSubmitting: false,
    isLoading: false,
    isFirstPeriod: false,
    isEditing: false,
    canEdit: false,
    status: "due",
    daysLeft: 0,
    billingMonthIndex: 0,
    deadlineMonthIndex: undefined,
    errors: () => ({}),
    dayMeterValue: null,
    nightMeterValue: null,
    previousDayMeterValue: null,
    previousNightMeterValue: null,
  });

  defineEmits<{
    "update:dayMeterValue": [value: number | null];
    "update:nightMeterValue": [value: number | null];
    submit: [];
    edit: [];
  }>();

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  const headlineId = "submission-headline";

  const normalizedDeadline = computed<SubmissionDeadline>(() => {
    const legacyDeadline = props.deadline ?? {
      status: props.status ?? "due",
      daysLeft: props.daysLeft ?? 0,
      billingMonthIndex: props.billingMonthIndex ?? 0,
      deadlineMonthIndex: props.deadlineMonthIndex ?? getDeadlineMonthIndex(),
    };

    return {
      status: legacyDeadline.status,
      daysLeft: legacyDeadline.daysLeft,
      billingMonthIndex: legacyDeadline.billingMonthIndex,
      deadlineMonthIndex: legacyDeadline.deadlineMonthIndex,
    };
  });

  const normalizedForm = computed<SubmissionFormState>(() => {
    if (props.form) {
      return props.form;
    }

    return {
      errors: props.errors ?? {},
      dayValue: props.dayMeterValue ?? null,
      nightValue: props.nightMeterValue ?? null,
      previousDayValue: props.previousDayMeterValue,
      previousNightValue: props.previousNightMeterValue,
    };
  });

  const normalizedSubmission = computed<SubmissionValues | null>(() => {
    if (props.submission) {
      return props.submission;
    }

    if (
      props.submittedAt == null &&
      props.submittedDayValue == null &&
      props.submittedNightValue == null &&
      props.lastPeriod == null
    ) {
      return null;
    }

    return {
      submittedAt: props.submittedAt,
      dayValue: props.submittedDayValue,
      nightValue: props.submittedNightValue,
      usage: props.lastPeriod,
    };
  });

  // Editing reopens the form over an already-submitted period, so the flag has
  // to override the status-derived view rather than being implied by it.
  const showSubmittedView = computed(
    () =>
      !props.isEditing &&
      (normalizedDeadline.value.status === "submitted" ||
        normalizedDeadline.value.status === "submitted-late")
  );

  // The submit window is closed in both these statuses; editing doesn't reopen
  // it, so late styling stays keyed on status alone, not on showSubmittedView.
  const isLate = computed(
    () =>
      normalizedDeadline.value.status === "overdue" ||
      normalizedDeadline.value.status === "submitted-late"
  );

  const copyInput = computed(() => ({
    status: normalizedDeadline.value.status,
    daysLeft: normalizedDeadline.value.daysLeft,
    deadlineMonthIndex: normalizedDeadline.value.deadlineMonthIndex,
    isFirstPeriod: props.isFirstPeriod ?? false,
    submittedAt: normalizedSubmission.value?.submittedAt,
    intlLocale: intlLocale.value,
  }));

  const { headline, subline, submitLabel } = useSubmissionCopy(copyInput);

  const periodLabel = computed(() =>
    t(`months.long.${normalizedDeadline.value.billingMonthIndex}`).toUpperCase()
  );
</script>

<style scoped lang="scss">
  // One bordered box wrapping the form at every width — no rail column left
  // to justify a separate lg layout for the outer wrapper.
  .submission {
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-lg);

    &--overdue {
      border-color: color-mix(in srgb, var(--s-red-500), transparent 70%);
    }

    &__main {
      @include layout.stack(var(--s-app-space-3));
      // One step up from .card's mobile padding: space-2 is too tight at 360px.
      padding: var(--s-app-space-3);

      @include layout.respond-to("lg") {
        gap: var(--s-app-space-4);
        padding: var(--s-app-space-4);
      }
    }

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
      font-size: 1.5rem;
      font-weight: 700;
      line-height: 1.2;
      letter-spacing: -0.01em;
      color: var(--s-content-color);

      .pi {
        font-size: 0.7em;
        flex-shrink: 0;
      }

      @include layout.respond-to("lg") {
        font-size: 1.75rem;
      }
    }

    &__subline {
      margin: 0;
      font-size: 0.9rem;
      color: var(--s-content-secondary-color);
    }

    &__form,
    &__values {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
    }

    &__badge-skel {
      border-radius: 2rem;
    }
  }
</style>

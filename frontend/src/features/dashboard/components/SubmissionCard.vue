<template>
  <div class="submission" :class="`submission--${status}`">
    <section class="submission__main" :aria-labelledby="headlineId">
      <header class="submission__header">
        <span class="submission__period">{{ periodLabel }}</span>

        <Skeleton v-if="isLoading" height="1.5rem" width="110px" class="submission__badge-skel" />
        <DeadlineBadge v-else :status="status" />
      </header>

      <template v-if="isLoading">
        <Skeleton height="1.75rem" width="80%" class="submission__skel" />
        <Skeleton height="1rem" width="60%" class="submission__skel" />
        <Skeleton height="0.375rem" width="100%" class="submission__skel" />
        <Skeleton height="2.75rem" class="submission__skel-input" />
        <Skeleton height="3.25rem" class="submission__skel-input" />
      </template>

      <template v-else>
        <div class="submission__status" role="status" aria-live="polite">
          <h2 :id="headlineId" class="submission__headline">
            <i v-if="isSubmitted" class="pi pi-check-circle" aria-hidden="true"></i>
            {{ headline }}
          </h2>
          <p class="submission__subline">{{ subline }}</p>
        </div>

        <!-- Submitted: values replace the form until the next period opens. -->
        <template v-if="isSubmitted">
          <div class="submission__values">
            <div v-for="tile in submittedTiles" :key="tile.key" class="submission__value-tile">
              <span class="submission__value-label">
                <i :class="tile.icon" :data-part="tile.key" aria-hidden="true"></i>
                {{ tile.label }}
              </span>
              <span class="submission__value-num">{{ tile.meterValue }}</span>
              <span v-if="tile.usage" class="submission__value-usage">{{ tile.usage }}</span>
            </div>
          </div>

          <p v-if="chargedThisPeriod" class="submission__charge">
            <i class="pi pi-receipt" aria-hidden="true"></i>
            {{ t("dashboard.chargedThisPeriod") }}
            <strong class="submission__charge-value">{{ chargedThisPeriod }}</strong>
          </p>

          <!-- Editing needs a backend update endpoint (issue #57); until that
               lands, don't render a button that can only fail, nor the lock
               note promising an edit the resident can't make. -->
          <div v-if="canEdit" class="submission__footer">
            <p class="submission__lock-note">{{ t("meterReadings.lockNote") }}</p>
            <Button
              class="submission__edit-btn"
              severity="secondary"
              :outlined="true"
              :label="t('meterReadings.editSubmitted')"
              @click="$emit('edit')"
            />
          </div>
        </template>

        <template v-else>
          <WindowStrip class="submission__strip" :is-overdue="status === 'overdue'" />

          <div class="submission__form">
            <div class="submission__field">
              <label for="submission-day" class="submission__field-label">
                <i class="pi pi-sun" data-part="day" aria-hidden="true"></i>
                {{ t("meterReadings.day") }}
              </label>
              <InputNumber
                input-id="submission-day"
                v-model="dayValueModel"
                inputmode="numeric"
                :placeholder="t('meterReadings.meterValuePlaceholder')"
                :min="0"
                :use-grouping="false"
                :invalid="!!errors.dayMeterValue"
                :pt="{
                  pcInputText: {
                    root: {
                      'aria-invalid': !!errors.dayMeterValue,
                      'aria-describedby': errors.dayMeterValue ? 'submission-day-error' : undefined,
                    },
                  },
                }"
                fluid
              />
              <span
                v-if="errors.dayMeterValue"
                id="submission-day-error"
                role="alert"
                class="submission__field-error"
              >
                {{ t(errors.dayMeterValue) }}
              </span>
              <span v-else-if="lastDayValue" class="submission__field-hint">
                {{ t("dashboard.lastSubmittedValue", { value: lastDayValue }) }}
              </span>
            </div>

            <div class="submission__field">
              <label for="submission-night" class="submission__field-label">
                <i class="pi pi-moon" data-part="night" aria-hidden="true"></i>
                {{ t("meterReadings.night") }}
              </label>
              <InputNumber
                input-id="submission-night"
                v-model="nightValueModel"
                inputmode="numeric"
                :placeholder="t('meterReadings.meterValuePlaceholder')"
                :min="0"
                :use-grouping="false"
                :invalid="!!errors.nightMeterValue"
                :pt="{
                  pcInputText: {
                    root: {
                      'aria-invalid': !!errors.nightMeterValue,
                      'aria-describedby': errors.nightMeterValue
                        ? 'submission-night-error'
                        : undefined,
                    },
                  },
                }"
                fluid
              />
              <span
                v-if="errors.nightMeterValue"
                id="submission-night-error"
                role="alert"
                class="submission__field-error"
              >
                {{ t(errors.nightMeterValue) }}
              </span>
              <span v-else-if="lastNightValue" class="submission__field-hint">
                {{ t("dashboard.lastSubmittedValue", { value: lastNightValue }) }}
              </span>
            </div>
          </div>

          <div class="submission__actions">
            <p v-if="errors.form" class="submission__form-error" role="alert">
              <i class="pi pi-times-circle" aria-hidden="true"></i>
              {{ t(errors.form) }}
            </p>

            <p v-if="status === 'overdue'" class="submission__note">
              <i class="pi pi-shield" aria-hidden="true"></i>
              {{ t("meterReadings.lateApprovalNote") }}
            </p>

            <Button
              class="submission__btn"
              :label="submitLabel"
              :severity="status === 'overdue' ? 'danger' : undefined"
              :loading="isSubmitting"
              :aria-busy="isSubmitting"
              @click="$emit('submit')"
            />

            <p v-if="status !== 'overdue'" class="submission__caption">
              {{ t("meterReadings.hintText") }}
            </p>
          </div>
        </template>
      </template>

      <p v-if="lastPeriodLine" class="submission__last-period">
        <i class="pi pi-history" aria-hidden="true"></i>
        {{ lastPeriodLine }}
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type { PeriodUsage } from "@/features/dashboard/composables/useUsageInsights";
  import type { FieldErrors } from "@/features/dashboard/types";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import type { DeadlineStatus } from "@shared/utils/deadline";
  import { DEADLINE_DAY } from "@shared/utils/deadline";
  import { formatKwh, formatMeterValue, formatUah } from "@shared/utils/format";

  import DeadlineBadge from "./DeadlineBadge.vue";
  import WindowStrip from "./WindowStrip.vue";

  interface Props {
    status: DeadlineStatus;
    daysLeft: number;
    billingMonthIndex: number;
    errors: FieldErrors;
    dayMeterValue: number | null;
    nightMeterValue: number | null;
    isSubmitting: boolean;
    isLoading: boolean;
    isFirstPeriod?: boolean | undefined;
    /** Reopens the form over a submitted period, until the edit is saved. */
    isEditing?: boolean | undefined;
    /** Off until the backend supports updating a submitted reading (#57). */
    canEdit?: boolean | undefined;
    submittedAt?: string | null | undefined;
    submittedDayValue?: number | string | null | undefined;
    submittedNightValue?: number | string | null | undefined;
    /** Used for the last-period hint and the previous-value input hints. */
    lastPeriod?: PeriodUsage | null | undefined;
    previousDayMeterValue?: number | string | null | undefined;
    previousNightMeterValue?: number | string | null | undefined;
  }

  const props = defineProps<Props>();

  const emit = defineEmits<{
    "update:dayMeterValue": [value: number | null];
    "update:nightMeterValue": [value: number | null];
    submit: [];
    edit: [];
  }>();

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  const headlineId = "submission-headline";

  // Editing reopens the form over an already-submitted period, so the flag has
  // to override the status-derived view rather than being implied by it.
  const isSubmitted = computed(
    () => !props.isEditing && (props.status === "submitted" || props.status === "submitted-late")
  );

  const monthName = computed(() => t(`months.long.${props.billingMonthIndex}`));
  const periodLabel = computed(() => monthName.value.toUpperCase());

  const kwh = computed(() => t("units.kwh"));

  function meter(value: number | string | null | undefined): string {
    return formatMeterValue(value, intlLocale.value);
  }

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
      default:
        return t("deadlineStatus.windowClosedAt", {
          day: DEADLINE_DAY,
          month: monthName.value,
        });
    }
  });

  const submitLabel = computed(() => {
    if (props.status === "overdue") {
      return t("meterReadings.submitLate");
    }
    return props.isFirstPeriod ? t("meterReadings.submitFirst") : t("meterReadings.submit");
  });

  const lastDayValue = computed(() =>
    props.previousDayMeterValue == null
      ? ""
      : formatKwh(props.previousDayMeterValue, intlLocale.value, kwh.value)
  );

  const lastNightValue = computed(() =>
    props.previousNightMeterValue == null
      ? ""
      : formatKwh(props.previousNightMeterValue, intlLocale.value, kwh.value)
  );

  const submittedTiles = computed(() => [
    {
      key: "day",
      icon: "pi pi-sun",
      label: t("meterReadings.day"),
      meterValue: meter(props.submittedDayValue),
      usage: props.lastPeriod
        ? t("dashboard.usedThisPeriod", {
            value: formatKwh(props.lastPeriod.dayKwh, intlLocale.value, kwh.value),
          })
        : "",
    },
    {
      key: "night",
      icon: "pi pi-moon",
      label: t("meterReadings.night"),
      meterValue: meter(props.submittedNightValue),
      usage: props.lastPeriod
        ? t("dashboard.usedThisPeriod", {
            value: formatKwh(props.lastPeriod.nightKwh, intlLocale.value, kwh.value),
          })
        : "",
    },
  ]);

  const chargedThisPeriod = computed(() => {
    const charged = props.lastPeriod?.chargedUah;
    return charged == null ? "" : formatUah(charged, intlLocale.value);
  });

  const lastPeriodLine = computed(() => {
    if (!props.lastPeriod) {
      return "";
    }

    return t("dashboard.lastPeriodSummary", {
      month: props.lastPeriod.monthLong,
      value: formatKwh(props.lastPeriod.totalKwh, intlLocale.value, kwh.value),
    });
  });

  const dayValueModel = computed({
    get: () => props.dayMeterValue,
    set: (value) => emit("update:dayMeterValue", value),
  });

  const nightValueModel = computed({
    get: () => props.nightMeterValue,
    set: (value) => emit("update:nightMeterValue", value),
  });
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

    &__strip {
      padding-bottom: var(--s-app-space-3);
      border-bottom: 1px solid var(--s-content-border-color);
    }

    &__form {
      display: flex;
      flex-direction: column;
      gap: var(--s-app-space-3);

      @include layout.respond-to("sm") {
        display: grid;
        grid-template-columns: 1fr 1fr;
      }
    }

    &__field {
      @include layout.stack(var(--s-app-space-1));
      min-width: 0;

      &-label {
        display: inline-flex;
        align-items: center;
        gap: var(--s-app-space-2);
        font-size: 0.82rem;
        font-weight: 600;
        color: var(--s-content-color);

        .pi {
          font-size: 1rem;

          &[data-part="day"] {
            color: var(--s-amber-500);
          }

          &[data-part="night"] {
            color: var(--s-primary-900);
          }
        }
      }

      &-error {
        font-size: 0.75rem;
        color: var(--s-red-500);
      }

      &-hint {
        font-size: 0.75rem;
        color: color-mix(in srgb, var(--s-content-color), transparent 45%);
      }

      :deep(input) {
        min-height: 2.75rem;
        border-radius: var(--s-app-radius-md);
      }
    }

    &__actions {
      @include layout.stack(var(--s-app-space-2));
      margin-top: auto;
      padding-top: var(--s-app-space-3);
      border-top: 1px solid var(--s-content-border-color);

      @include layout.respond-to("lg") {
        flex-direction: row-reverse;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
      }
    }

    &__btn {
      width: 100%;
      min-height: 3.25rem;
      border-radius: var(--s-app-radius-md);

      @include layout.respond-to("lg") {
        width: auto;
        min-height: 2.75rem;
      }
    }

    &__caption,
    &__lock-note {
      margin: 0;
      font-size: 0.78rem;
      color: var(--s-content-secondary-color);

      @include layout.respond-to("lg") {
        flex: 1;
        min-width: 0;
      }
    }

    &__form-error {
      display: flex;
      align-items: flex-start;
      gap: var(--s-app-space-2);
      margin: 0;
      padding: var(--s-app-space-2);
      border-radius: var(--s-app-radius-sm);
      background: color-mix(in srgb, var(--s-red-500), transparent 88%);
      font-size: 0.78rem;
      color: var(--s-red-700);
      flex-basis: 100%;

      .pi {
        font-size: 0.85rem;
        flex-shrink: 0;
        margin-top: 0.15em;
      }
    }

    &__note {
      display: flex;
      align-items: flex-start;
      gap: var(--s-app-space-2);
      margin: 0;
      font-size: 0.78rem;
      color: var(--s-content-secondary-color);
      flex-basis: 100%;

      .pi {
        font-size: 0.85rem;
        flex-shrink: 0;
        margin-top: 0.15em;
        color: var(--s-red-500);
      }
    }

    &__values {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--s-app-space-3);
    }

    &__value-tile {
      @include layout.stack(var(--s-app-space-1));
      min-width: 0;
      padding: var(--s-app-space-3);
      border-radius: var(--s-app-radius-md);
      background: color-mix(in srgb, var(--s-content-color), transparent 94%);
    }

    &__value-label {
      display: inline-flex;
      align-items: center;
      gap: var(--s-app-space-1);
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--s-content-secondary-color);

      .pi[data-part="day"] {
        color: var(--s-amber-500);
      }

      .pi[data-part="night"] {
        color: var(--s-primary-900);
      }
    }

    &__value-num {
      font-size: 1.15rem;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
      color: var(--s-content-color);
    }

    &__value-usage {
      font-size: 0.75rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    }

    &__charge {
      display: flex;
      align-items: center;
      gap: var(--s-app-space-2);
      margin: 0;
      font-size: 0.85rem;
      color: var(--s-content-secondary-color);

      .pi {
        flex-shrink: 0;
        color: var(--s-primary-900);
      }
    }

    &__charge-value {
      color: var(--s-content-color);
      font-variant-numeric: tabular-nums;
    }

    &__footer {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: var(--s-app-space-2);
      margin-top: auto;
      padding-top: var(--s-app-space-3);
      border-top: 1px solid var(--s-content-border-color);

      @include layout.respond-to("sm") {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
      }
    }

    &__edit-btn {
      width: 100%;
      min-height: 3.25rem;
      flex-shrink: 0;

      @include layout.respond-to("sm") {
        width: auto;
        min-height: 2.75rem;
      }
    }

    &__last-period {
      display: flex;
      align-items: center;
      gap: var(--s-app-space-2);
      margin: 0;
      padding-top: var(--s-app-space-3);
      border-top: 1px solid var(--s-content-border-color);
      font-size: 0.8rem;
      color: var(--s-content-secondary-color);

      .pi {
        flex-shrink: 0;
      }
    }

    &__badge-skel {
      border-radius: 2rem;
    }

    &__skel {
      border-radius: var(--s-app-radius-sm);
    }

    &__skel-input {
      border-radius: var(--s-app-radius-md);
    }
  }
</style>

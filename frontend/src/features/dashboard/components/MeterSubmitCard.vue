<template>
  <div class="card submit-card">
    <div class="submit-card__header">
      <div class="submit-card__header-content">
        <span class="submit-card__icon-wrap">
          <i class="pi pi-calendar" aria-hidden="true"></i>
        </span>
        <h3 class="submit-card__title">
          {{ t("submitMeter.title", { month: t(`months.long.${billingMonthIndex}`) }) }}
        </h3>
      </div>

      <template v-if="isLoading">
        <Skeleton height="1.5rem" width="120px" class="submit-card__skeleton-badge" />
      </template>
      <template v-else>
        <DeadlineBadge :reading="latestReading" />
      </template>
    </div>

    <template v-if="isLoading">
      <div class="submit-card__form">
        <div class="submit-card__field">
          <Skeleton height="1rem" width="40%" class="submit-card__skeleton-label" />
          <Skeleton height="2.75rem" class="submit-card__skeleton-input" />
        </div>
        <div class="submit-card__field">
          <Skeleton height="1rem" width="40%" class="submit-card__skeleton-label" />
          <Skeleton height="2.75rem" class="submit-card__skeleton-input" />
        </div>
        <Skeleton height="2.5rem" width="100px" class="submit-card__skeleton-button" />
      </div>
      <Skeleton height="1rem" width="60%" class="submit-card__skeleton-note" />
    </template>

    <template v-else-if="isSubmitted">
      <div class="submit-card__submitted-readings">
        <div class="submit-card__meter-row">
          <span class="submit-card__zone submit-card__zone--day">
            <i class="pi pi-sun" aria-hidden="true"></i>
            {{ t("meterReadings.day") }}
          </span>
          <span class="submit-card__meter-num">{{
            formatValue(latestReading?.day_meter_value)
          }}</span>
        </div>
        <div class="submit-card__meter-row">
          <span class="submit-card__zone submit-card__zone--night">
            <i class="pi pi-moon" aria-hidden="true"></i>
            {{ t("meterReadings.night") }}
          </span>
          <span class="submit-card__meter-num">{{
            formatValue(latestReading?.night_meter_value)
          }}</span>
        </div>
      </div>
      <div v-if="submittedStatus === 'submitted'" class="submit-card__note">
        <i class="pi pi-check-circle" aria-hidden="true"></i>
        {{ t("submitMeter.note.submitted") }}
      </div>
      <div v-else-if="submittedStatus === 'submitted-late'" class="submit-card__note">
        <i class="pi pi-exclamation-circle" aria-hidden="true"></i>
        {{ t("submitMeter.note.submittedLate", { deadline: deadlineDate }) }}
      </div>
    </template>

    <template v-else>
      <div class="submit-card__form">
        <div class="submit-card__field">
          <label class="submit-card__field-label">
            <i
              class="pi pi-sun submit-card__input-icon submit-card__input-icon--day"
              aria-hidden="true"
            ></i>
            {{ t("meterReadings.day") }}
          </label>
          <InputNumber
            v-model="dayValueModel"
            class="submit-card__input"
            placeholder="1234"
            :min="0"
            :use-grouping="false"
            :invalid="!!errors.dayMeterValue"
            fluid
          />
          <span v-if="errors.dayMeterValue" class="submit-card__field-error">{{
            t(errors.dayMeterValue)
          }}</span>
        </div>
        <div class="submit-card__field">
          <label class="submit-card__field-label">
            <i
              class="pi pi-moon submit-card__input-icon submit-card__input-icon--night"
              aria-hidden="true"
            ></i>
            {{ t("meterReadings.night") }}
          </label>
          <InputNumber
            v-model="nightValueModel"
            class="submit-card__input"
            placeholder="5678"
            :min="0"
            :use-grouping="false"
            :invalid="!!errors.nightMeterValue"
            fluid
          />
          <span v-if="errors.nightMeterValue" class="submit-card__field-error">{{
            t(errors.nightMeterValue)
          }}</span>
        </div>
      </div>
      <div v-if="isOverdue" class="submit-card__note">
        <i class="pi pi-shield" aria-hidden="true"></i>
        {{ t("submitMeter.note.overdue") }}
      </div>
      <div v-else class="submit-card__note">
        <i class="pi pi-info-circle" aria-hidden="true"></i>
        {{ t("submitMeter.note.due") }}
      </div>
      <Button
        class="submit-card__btn"
        :label="t('common.submit')"
        :loading="isSubmitting"
        @click="$emit('submit')"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
  import Button from "primevue/button";
  import InputNumber from "primevue/inputnumber";
  import Skeleton from "primevue/skeleton";
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type { FieldErrors } from "@/features/dashboard/types";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { getDeadlineStatus, getSubmitWindow } from "@/features/meter-readings/deadline";
  import type { MeterReadingOut } from "@shared/api/meter-readings";

  import DeadlineBadge from "./DeadlineBadge.vue";

  interface Props {
    isOverdue: boolean;
    isSubmitting: boolean;
    isLoading: boolean;
    errors: FieldErrors;
    dayMeterValue: number | null;
    nightMeterValue: number | null;
    latestReading: MeterReadingOut | null;
    isSubmitted: boolean;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<{
    "update:dayMeterValue": [value: number | null];
    "update:nightMeterValue": [value: number | null];
    submit: [];
  }>();

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  const billingMonthIndex = computed(() => new Date().getMonth() - 1);

  const submittedStatus = computed(() => getDeadlineStatus(props.latestReading?.submitted_at));

  const deadlineDate = computed(() => {
    const { end } = getSubmitWindow();
    return end.toLocaleDateString(intlLocale.value);
  });

  const dayValueModel = computed({
    get: () => props.dayMeterValue,
    set: (v) => emit("update:dayMeterValue", v),
  });

  const nightValueModel = computed({
    get: () => props.nightMeterValue,
    set: (v) => emit("update:nightMeterValue", v),
  });

  function formatValue(value: number | string | undefined): string {
    if (value == null) return "—";
    const numeric = typeof value === "string" ? Number(value) : value;
    return numeric.toLocaleString(intlLocale.value, { maximumFractionDigits: 2 });
  }
</script>

<style scoped lang="scss">
  .submit-card {
    display: flex;
    flex-direction: column;
    min-height: 16rem;
    max-width: 37.5rem;

    &__header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--s-app-space-3);
      flex-wrap: wrap;
      flex-shrink: 0;

      &-content {
        display: flex;
        align-items: center;
        gap: var(--s-app-space-3);
      }
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
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--s-content-color);
    }

    &__window {
      font-size: 0.8rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      margin-top: 0.1rem;
    }

    &__label {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--s-content-color);
    }

    &__form {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--s-app-space-3);
    }

    &__field {
      @include layout.stack(var(--s-app-space-1));

      &-label {
        display: inline-flex;
        align-items: center;
        gap: var(--s-app-space-2);
        font-size: 0.82rem;
        font-weight: 600;
        color: var(--s-content-color);
      }

      &-error {
        font-size: 0.75rem;
        color: var(--s-red-500);
      }
    }

    &__input-icon {
      font-size: 1rem;

      &--day {
        color: var(--s-amber-500);
      }
      &--night {
        color: var(--s-primary-900);
      }
    }

    &__btn {
      align-self: flex-end;
      width: fit-content;
    }

    &__note {
      display: flex;
      align-items: flex-start;
      gap: var(--s-app-space-2);
      font-size: 0.78rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);

      .pi {
        font-size: 0.85rem;
        flex-shrink: 0;
        margin-top: 0.15em;
      }
    }

    &__submitted-readings {
      @include layout.stack(var(--s-app-space-2));
    }

    &__meter-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: var(--s-app-space-2);
    }

    &__zone {
      display: inline-flex;
      align-items: center;
      gap: var(--s-app-space-2);
      font-size: 0.95rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 25%);

      &--day .pi {
        color: var(--s-amber-500);
      }
      &--night .pi {
        color: var(--s-primary-900);
      }
    }

    &__meter-num {
      font-size: 1.1rem;
      font-weight: 700;
    }

    &__skeleton-badge {
      border-radius: 2rem;
      align-self: center;
    }

    &__skeleton-label {
      border-radius: var(--s-app-radius-sm);
    }

    &__skeleton-input {
      border-radius: var(--s-app-radius-md);
    }

    &__skeleton-button {
      border-radius: var(--s-app-radius-md);
      grid-column: 1 / -1;
      margin-top: var(--s-app-space-2);
      justify-self: end;
    }

    &__skeleton-note {
      border-radius: var(--s-app-radius-sm);
    }
  }
</style>

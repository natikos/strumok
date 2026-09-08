<template>
  <div class="card submit-card">
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
      </div>
      <Skeleton height="1rem" width="60%" class="submit-card__skeleton-note" />
      <Skeleton height="3.25rem" class="submit-card__skeleton-button" />
    </template>

    <template v-else>
      <div class="submit-card__form">
        <div class="submit-card__field">
          <label for="submit-card-day" class="submit-card__field-label">
            <i
              class="pi pi-sun submit-card__input-icon submit-card__input-icon--day"
              aria-hidden="true"
            ></i>
            {{ t("meterReadings.day") }}
          </label>
          <InputNumber
            input-id="submit-card-day"
            v-model="dayValueModel"
            class="submit-card__input"
            inputmode="numeric"
            :placeholder="t('meterReadings.meterValuePlaceholder')"
            :min="0"
            :use-grouping="false"
            :invalid="!!errors.dayMeterValue"
            :pt="{
              pcInputText: {
                root: {
                  'aria-invalid': !!errors.dayMeterValue,
                  'aria-describedby': errors.dayMeterValue ? 'submit-card-day-error' : undefined,
                },
              },
            }"
            fluid
          />
          <span
            v-if="errors.dayMeterValue"
            id="submit-card-day-error"
            role="alert"
            class="submit-card__field-error"
            >{{ t(errors.dayMeterValue) }}</span
          >
        </div>
        <div class="submit-card__field">
          <label for="submit-card-night" class="submit-card__field-label">
            <i
              class="pi pi-moon submit-card__input-icon submit-card__input-icon--night"
              aria-hidden="true"
            ></i>
            {{ t("meterReadings.night") }}
          </label>
          <InputNumber
            input-id="submit-card-night"
            v-model="nightValueModel"
            class="submit-card__input"
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
                    ? 'submit-card-night-error'
                    : undefined,
                },
              },
            }"
            fluid
          />
          <span
            v-if="errors.nightMeterValue"
            id="submit-card-night-error"
            role="alert"
            class="submit-card__field-error"
            >{{ t(errors.nightMeterValue) }}</span
          >
        </div>
      </div>

      <div class="submit-card__actions">
        <div v-if="isOverdue" class="submit-card__note submit-card__note--overdue">
          <i class="pi pi-shield" aria-hidden="true"></i>
          {{ t("meterReadings.lateApprovalNote") }}
        </div>

        <Button
          class="submit-card__btn"
          :label="submitLabel"
          :severity="isOverdue ? 'danger' : undefined"
          :loading="isSubmitting"
          :aria-busy="isSubmitting"
          @click="$emit('submit')"
        />

        <p v-if="!isOverdue" class="submit-card__caption">{{ t("meterReadings.hintText") }}</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import type { FieldErrors } from "@/features/dashboard/types";

  interface Props {
    isOverdue: boolean;
    isSubmitting: boolean;
    isLoading: boolean;
    errors: FieldErrors;
    dayMeterValue: number | null;
    nightMeterValue: number | null;
    isFirstPeriod?: boolean;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<{
    "update:dayMeterValue": [value: number | null];
    "update:nightMeterValue": [value: number | null];
    submit: [];
  }>();

  const { t } = useI18n();

  const submitLabel = computed(() => {
    if (props.isOverdue) {
      return t("meterReadings.submitLate");
    }
    if (props.isFirstPeriod) {
      return t("meterReadings.submitFirst");
    }
    return t("meterReadings.submit");
  });

  const dayValueModel = computed({
    get: () => props.dayMeterValue,
    set: (v) => emit("update:dayMeterValue", v),
  });

  const nightValueModel = computed({
    get: () => props.nightMeterValue,
    set: (v) => emit("update:nightMeterValue", v),
  });
</script>

<style scoped lang="scss">
  .submit-card {
    display: flex;
    flex-direction: column;
    max-width: 37.5rem;

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

    &__actions {
      @include layout.stack(var(--s-app-space-2));
      padding-top: var(--s-app-space-3);
      border-top: 1px solid var(--s-content-border-color);
    }

    &__btn {
      width: 100%;
      min-height: 3.25rem;

      @include layout.respond-to("sm") {
        width: auto;
        align-self: flex-end;
      }
    }

    &__caption {
      margin: 0;
      font-size: 0.78rem;
      color: var(--s-content-secondary-color);
    }

    &__note {
      display: flex;
      align-items: flex-start;
      gap: var(--s-app-space-2);
      font-size: 0.78rem;
      color: var(--s-content-secondary-color);

      .pi {
        font-size: 0.85rem;
        flex-shrink: 0;
        margin-top: 0.15em;
      }

      &--overdue .pi {
        color: var(--s-red-500);
      }
    }

    &__skeleton-label {
      border-radius: var(--s-app-radius-sm);
    }

    &__skeleton-input {
      border-radius: var(--s-app-radius-md);
    }

    &__skeleton-button {
      border-radius: var(--s-app-radius-md);
      margin-top: var(--s-app-space-2);
    }

    &__skeleton-note {
      border-radius: var(--s-app-radius-sm);
    }
  }
</style>

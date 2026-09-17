<template>
  <div class="submission-form">
    <WindowStrip class="submission-form__strip" :is-overdue="isLate" />

    <div class="submission-form__fields">
      <MeterValueField
        part="day"
        :model-value="dayValue"
        :error="errors.dayMeterValue"
        :hint="dayHint"
        @update:model-value="$emit('update:dayValue', $event)"
      />
      <MeterValueField
        part="night"
        :model-value="nightValue"
        :error="errors.nightMeterValue"
        :hint="nightHint"
        @update:model-value="$emit('update:nightValue', $event)"
      />
    </div>

    <div class="submission-form__actions">
      <p v-if="errors.form" class="submission__form-error" role="alert">
        <i class="pi pi-times-circle" aria-hidden="true"></i>
        {{ t(errors.form) }}
      </p>

      <p v-if="isLate" class="submission__note">
        <i class="pi pi-shield" aria-hidden="true"></i>
        {{ t("meterReadings.lateApprovalNote") }}
      </p>

      <Button
        class="submission-form__submit-btn"
        :label="submitLabel"
        :severity="isLate ? 'danger' : undefined"
        :loading="isSubmitting"
        :aria-busy="isSubmitting"
        @click="$emit('submit')"
      />

      <p v-if="!isLate" class="submission__caption">
        {{ t("meterReadings.hintText") }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";

  import type { FieldErrors } from "@/features/dashboard/types";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { formatKwh } from "@shared/utils/format";

  import MeterValueField from "./MeterValueField.vue";
  import WindowStrip from "./WindowStrip.vue";

  interface Props {
    isLate: boolean;
    errors: FieldErrors;
    dayValue: number | null;
    nightValue: number | null;
    previousDayValue?: number | string | null | undefined;
    previousNightValue?: number | string | null | undefined;
    isSubmitting: boolean;
    submitLabel: string;
  }

  const props = defineProps<Props>();

  defineEmits<{
    "update:dayValue": [value: number | null];
    "update:nightValue": [value: number | null];
    submit: [];
  }>();

  const { t } = useI18n();
  const { intlLocale } = useLocale();

  const kwh = t("units.kwh");

  const dayHint = props.previousDayValue == null ? undefined : hint(props.previousDayValue);
  const nightHint = props.previousNightValue == null ? undefined : hint(props.previousNightValue);

  function hint(value: number | string): string {
    return t("dashboard.lastSubmittedValue", {
      value: formatKwh(value, intlLocale.value, kwh),
    });
  }
</script>

<style scoped lang="scss">
  .submission-form {
    &__strip {
      padding-bottom: var(--s-app-space-3);
      border-bottom: 1px solid var(--s-content-border-color);
    }

    &__fields {
      display: flex;
      flex-direction: column;
      gap: var(--s-app-space-3);
      margin-top: var(--s-app-space-3);

      @include layout.respond-to("sm") {
        display: grid;
        grid-template-columns: 1fr 1fr;
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

    &__submit-btn {
      width: 100%;
      min-height: 3.25rem;
      border-radius: var(--s-app-radius-md);

      @include layout.respond-to("lg") {
        width: auto;
        min-height: 2.75rem;
      }
    }

    &__caption {
      margin: 0;
      font-size: 0.78rem;
      color: var(--s-content-secondary-color);

      @include layout.respond-to("lg") {
        flex: 1;
        min-width: 0;
      }
    }

    &__error {
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
  }
</style>

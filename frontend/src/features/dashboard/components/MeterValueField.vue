<template>
  <div class="meter-value-field">
    <label :for="inputId" class="meter-value-field__label">
      <i :class="icon" :data-part="part" aria-hidden="true"></i>
      {{ label }}
    </label>
    <InputNumber
      :input-id="inputId"
      :model-value="modelValue"
      inputmode="numeric"
      :placeholder="t('meterReadings.meterValuePlaceholder')"
      :min="0"
      :use-grouping="false"
      :invalid="!!error"
      :pt="{
        pcInputText: {
          root: {
            'aria-invalid': !!error,
            'aria-describedby': error ? errorId : undefined,
          },
        },
      }"
      fluid
      @update:model-value="$emit('update:modelValue', $event ?? null)"
    />
    <span v-if="error" :id="errorId" role="alert" class="meter-value-field__error">
      {{ t(error) }}
    </span>
    <span v-else-if="hint" class="meter-value-field__hint submission__field-hint">
      {{ hint }}
    </span>
  </div>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  interface Props {
    part: "day" | "night";
    modelValue: number | null;
    error?: string | undefined;
    hint?: string | undefined;
  }

  const props = defineProps<Props>();

  defineEmits<{
    "update:modelValue": [value: number | null];
  }>();

  const { t } = useI18n();

  const inputId = `submission-${props.part}`;
  const errorId = `${inputId}-error`;

  const icon = computed(() => (props.part === "day" ? "pi pi-sun" : "pi pi-moon"));
  const label = computed(() => t(`meterReadings.${props.part}`));
</script>

<style scoped lang="scss">
  .meter-value-field {
    @include layout.stack(var(--s-app-space-1));
    min-width: 0;

    &__label {
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

    &__error {
      font-size: 0.75rem;
      color: var(--s-red-500);
    }

    &__hint {
      font-size: 0.75rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    }

    :deep(input) {
      min-height: 2.75rem;
      border-radius: var(--s-app-radius-md);
    }
  }
</style>

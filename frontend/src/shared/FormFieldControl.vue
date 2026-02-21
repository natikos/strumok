<template>
  <FormField v-slot="$field" :name="name" class="form-field-control">
    <Typography variant="label" class="form-field-control__label" :for="id">
      {{ $t(labelKey) }}
    </Typography>

    <Password
      v-if="type === 'password'"
      :id="id"
      class="form-field-control__control"
      :name="name"
      :feedback="false"
      fluid
      toggle-mask
      :placeholder="$t(placeholderKey)"
      :disabled="disabled"
      :invalid="$field.invalid"
    />

    <InputText
      v-else
      :id="id"
      class="form-field-control__control"
      :type="type"
      :name="name"
      :placeholder="$t(placeholderKey)"
      :disabled="disabled"
      :invalid="$field.invalid"
    />

    <div class="form-field-control__message">
      <Transition name="field-error">
        <Typography
          v-if="$field.invalid && $field.error?.message"
          variant="caption"
          class="form-field-control__error"
        >
          {{ $t($field.error.message) }}
        </Typography>
      </Transition>
    </div>
  </FormField>
</template>

<script setup lang="ts">
  import { FormField } from "@primevue/forms";

  import Typography from "@shared/Typography.vue";

  interface FormFieldControlProps {
    disabled?: boolean;
    id: string;
    labelKey: string;
    name: string;
    placeholderKey: string;
    type?: "text" | "email" | "password";
  }

  withDefaults(defineProps<FormFieldControlProps>(), {
    disabled: false,
    type: "text",
  });
</script>

<style scoped lang="scss">
  .form-field-control {
    min-width: 0;
  }

  .form-field-control__control {
    width: 100%;
  }

  .form-field-control__error {
    color: var(--s-red-500);
    display: block;
  }

  .field-error-enter-active,
  .field-error-leave-active {
    transition:
      max-height 180ms ease,
      opacity 180ms ease,
      transform 180ms ease;
  }

  .field-error-enter-from,
  .field-error-leave-to {
    max-height: 0;
    opacity: 0;
    transform: translateY(-0.2rem);
  }

  .field-error-enter-to,
  .field-error-leave-from {
    max-height: 1.2rem;
    opacity: 1;
    transform: translateY(0);
  }

  .form-field-control :deep(.p-password-toggle-mask-icon) {
    cursor: pointer;
  }
</style>

<template>
  <div class="error-state" role="alert">
    <p class="error-state__message">{{ $t(messageKey) }}</p>
    <button class="error-state__retry" type="button" @click="$emit('retry')">
      {{ $t("errors.retry") }}
    </button>
  </div>
</template>

<script setup lang="ts">
  defineProps<{ messageKey: string }>();
  defineEmits<{ retry: [] }>();
</script>

<style scoped lang="scss">
  .error-state {
    align-items: center;
    background: color-mix(in srgb, var(--s-red-500), transparent 92%);
    border: 1px solid color-mix(in srgb, var(--s-red-500), transparent 65%);
    border-radius: var(--s-app-radius-md);
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-app-space-3);
    justify-content: space-between;
    padding: var(--s-app-space-3) var(--s-app-space-4);

    &__message {
      color: var(--s-content-color);
      margin: 0;
    }

    &__retry {
      background: var(--s-primary-color);
      border: 0;
      border-radius: var(--s-app-radius-sm);
      color: white;
      cursor: pointer;
      font: inherit;
      font-weight: 600;
      padding: 0.5rem 0.75rem;
    }
  }
</style>

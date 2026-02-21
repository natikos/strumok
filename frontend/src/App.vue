<template>
  <RouterView />
</template>

<script setup lang="ts">
  import { onMounted } from "vue";
  import { RouterView } from "vue-router";

  import { useLocale } from "@features/i18n/composables/useLocale";
  import { useTheme } from "@features/theme/composables/useTheme";

  const { initializeLocale } = useLocale();
  const { initializeTheme } = useTheme();

  onMounted(() => {
    initializeLocale();
    initializeTheme();
  });
</script>

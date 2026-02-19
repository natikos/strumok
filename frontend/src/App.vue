<template>
  <RouterView />
</template>

<script setup lang="ts">
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { useTheme } from "@/features/theme/composables/useTheme";
  import { onMounted } from "vue";
  import { RouterView } from "vue-router";

  const { initializeLocale } = useLocale();
  const { initializeTheme } = useTheme();

  onMounted(() => {
    initializeLocale();
    initializeTheme();
  });
</script>

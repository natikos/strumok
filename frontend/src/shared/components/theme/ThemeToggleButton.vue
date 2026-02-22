<template>
  <Button
    :icon="isDarkTheme ? 'pi pi-moon' : 'pi pi-sun'"
    variant="text"
    rounded
    :aria-label="isDarkTheme ? $t('layout.switchToLightTheme') : $t('layout.switchToDarkTheme')"
    :title="isDarkTheme ? $t('layout.switchToLightTheme') : $t('layout.switchToDarkTheme')"
    @click="handleToggle"
  />
</template>

<script setup lang="ts">
  import Button from "primevue/button";

  import type { ThemeMode } from "@features/preferences/preferences.storage";
  import { useTheme } from "@features/theme/composables/useTheme";

  const { isDarkTheme, toggleTheme } = useTheme();

  const emit = defineEmits<{
    toggle: [ThemeMode];
  }>();

  function handleToggle(): void {
    const nextTheme = toggleTheme();
    emit("toggle", nextTheme);
  }
</script>

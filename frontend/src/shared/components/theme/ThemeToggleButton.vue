<template>
  <Button
    variant="text"
    rounded
    :aria-label="isDarkTheme ? $t('layout.switchToLightTheme') : $t('layout.switchToDarkTheme')"
    :title="isDarkTheme ? $t('layout.switchToLightTheme') : $t('layout.switchToDarkTheme')"
    @click="handleToggle"
  >
    <component :is="themeIcon" />
  </Button>
</template>

<script setup lang="ts">
  import { Moon, Sun } from "@primeicons/vue";
  import { computed } from "vue";

  import type { ThemeMode } from "@features/preferences/preferences.storage";
  import { useTheme } from "@features/theme/composables/useTheme";

  const { isDarkTheme, toggleTheme } = useTheme();

  const themeIcon = computed(() => (isDarkTheme.value ? Moon : Sun));

  const emit = defineEmits<{
    toggle: [ThemeMode];
  }>();

  function handleToggle(): void {
    const nextTheme = toggleTheme();
    emit("toggle", nextTheme);
  }
</script>

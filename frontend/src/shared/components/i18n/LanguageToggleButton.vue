<template>
  <Button
    :label="currentLocale === 'ua' ? 'UA' : 'EN'"
    variant="text"
    rounded
    :aria-label="currentLocale === 'ua' ? $t('layout.switchToEnglish') : $t('layout.switchToUkrainian')"
    :title="currentLocale === 'ua' ? $t('layout.switchToEnglish') : $t('layout.switchToUkrainian')"
    @click="handleToggle"
  />
</template>

<script setup lang="ts">
  import Button from "primevue/button";

  import type { LanguageCode } from "@features/preferences/preferences.storage";
  import { useLocale } from "@features/i18n/composables/useLocale";

  const { currentLocale, toggleLocale } = useLocale();

  const emit = defineEmits<{
    toggle: [LanguageCode];
  }>();

  function handleToggle(): void {
    const nextLocale = toggleLocale();
    emit("toggle", nextLocale);
  }
</script>

<template>
  <header class="auth-layout__header">
    <img class="auth-layout__logo" src="/logo.svg" alt="Strumok Logo" />

    <div class="auth-layout__controls">
      <Button
        class="auth-layout__language-toggle"
        :label="languageLabel"
        variant="text"
        rounded
        :aria-label="languageAriaLabel"
        :title="languageAriaLabel"
        @click="toggleLocale"
      />
      <Button
        class="auth-layout__theme-toggle"
        :icon="themeIcon"
        variant="text"
        rounded
        :aria-label="themeAriaLabel"
        :title="themeAriaLabel"
        @click="toggleTheme"
      />
    </div>
  </header>

  <main class="auth-layout__main">
    <slot />
  </main>
</template>

<script setup lang="ts">
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { useTheme } from "@/features/theme/composables/useTheme";
  import Button from "primevue/button";
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  const { t } = useI18n();
  const { currentLocale, toggleLocale } = useLocale();
  const { theme, toggleTheme } = useTheme();

  const themeIcon = computed(() => (theme.value === "dark" ? "pi pi-moon" : "pi pi-sun"));

  const themeAriaLabel = computed(() =>
    theme.value === "dark" ? t("layout.switchToLightTheme") : t("layout.switchToDarkTheme")
  );

  const languageLabel = computed(() => (currentLocale.value === "ua" ? "UA" : "EN"));

  const languageAriaLabel = computed(() =>
    currentLocale.value === "ua" ? t("layout.switchToEnglish") : t("layout.switchToUkrainian")
  );
</script>

<style lang="scss" scoped>
  .auth-layout__header {
    align-items: center;
    display: flex;
    gap: var(--space-4);
    justify-content: space-between;
    min-height: 4.5rem;
    padding: var(--space-4) var(--space-4) 0;
  }

  .auth-layout__logo {
    display: block;
    height: auto;
    max-width: clamp(8rem, 6rem + 8vw, 12rem);
    width: 100%;
  }

  .auth-layout__controls {
    align-items: center;
    display: flex;
    gap: var(--space-2);
    justify-content: flex-end;
  }

  .auth-layout__main {
    margin-inline: auto;
    max-width: 30rem;
    padding: var(--space-8) var(--space-4) var(--space-10);
    width: 100%;
  }

  @media (min-width: 48rem) {
    .auth-layout__header {
      padding-inline: var(--space-8);
    }

    .auth-layout__main {
      padding-inline: var(--space-6);
      padding-top: var(--space-10);
    }
  }
</style>

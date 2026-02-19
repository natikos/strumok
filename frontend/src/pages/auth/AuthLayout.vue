<template>
  <div class="auth-layout">
    <header class="auth-layout__header">
      <img class="auth-layout__logo" src="/logo.svg?v=12312" alt="Strumok Logo" />

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
  </div>
</template>

<script setup lang="ts">
  import { useLocale } from "@features/i18n/composables/useLocale";
  import { useTheme } from "@features/theme/composables/useTheme";
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
  .auth-layout {
    @include layout.stack(0);
    height: 100vh;
    width: 100%;

    &__header {
      align-items: center;
      display: flex;
      gap: var(--s-app-space-3);
      justify-content: space-between;
      height: 3.5rem;
      padding: var(--s-app-space-2) var(--s-app-space-3) 0;
    }

    &__logo {
      display: block;
      max-width: 9.5rem;
      width: 100%;
    }

    &__controls {
      align-items: center;
      display: flex;
      gap: var(--s-app-space-2);
      justify-content: flex-end;
    }

    &__main {
      @include layout.stack(0);
      align-items: start;
      flex: 1;
      margin: 0 auto;
      max-width: 36rem;
      padding: var(--s-app-space-3) var(--s-app-space-3) var(--s-app-space-4);
      width: 100%;
    }

    @media (min-width: 48rem) {
      &__header {
        min-height: 4.5rem;
        padding: var(--s-app-space-4) var(--s-app-space-8) 0;
      }

      &__logo {
        max-width: 12rem;
      }

      &__main {
        align-items: center;
        padding: var(--s-app-space-10) var(--s-app-space-6) var(--s-app-space-12);
      }
    }
  }
</style>

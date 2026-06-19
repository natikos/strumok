<template>
  <div class="settings-page">
    <header class="settings-header">
      <h1 class="settings-header__title">{{ $t("settings.title") }}</h1>
    </header>

    <div class="settings-body">
      <section class="settings-section">
        <h2 class="settings-section__title">{{ $t("settings.appearance") }}</h2>

        <div class="settings-card">
          <div class="settings-row">
            <div class="settings-row__info">
              <i class="pi pi-palette settings-row__icon"></i>
              <div>
                <span class="settings-row__label">{{ $t("settings.theme") }}</span>
                <span class="settings-row__hint">{{ isDarkTheme ? $t("settings.themeDark") : $t("settings.themeLight") }}</span>
              </div>
            </div>
            <ThemeToggleButton @toggle="handlePreferenceToggle({ theme: $event })" />
          </div>

          <div class="settings-row">
            <div class="settings-row__info">
              <i class="pi pi-language settings-row__icon"></i>
              <div>
                <span class="settings-row__label">{{ $t("settings.language") }}</span>
                <span class="settings-row__hint">{{ currentLocale === 'ua' ? 'Українська' : 'English' }}</span>
              </div>
            </div>
            <LanguageToggleButton @toggle="handlePreferenceToggle({ language: $event })" />
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { useLocale } from "@features/i18n/composables/useLocale";
  import type { LanguageCode, ThemeMode } from "@features/preferences/preferences.storage";
  import { useTheme } from "@features/theme/composables/useTheme";
  import { updateMyPreferences } from "@shared/api/auth";
  import LanguageToggleButton from "@shared/components/i18n/LanguageToggleButton.vue";
  import ThemeToggleButton from "@shared/components/theme/ThemeToggleButton.vue";

  const { setLocale, currentLocale } = useLocale();
  const { setTheme, isDarkTheme } = useTheme();

  async function handlePreferenceToggle(payload: {
    language?: LanguageCode;
    theme?: ThemeMode;
  }): Promise<void> {
    const updated = await updateMyPreferences(payload);
    setLocale(updated.language);
    setTheme(updated.theme);
  }
</script>

<style scoped lang="scss">
  .settings-page {
    padding: var(--s-app-space-5);

    @media (min-width: 60rem) {
      padding: var(--s-app-space-8);
    }
  }

  .settings-header {
    margin-bottom: var(--s-app-space-6);

    &__title {
      color: var(--s-content-color);
      font-size: 1.6rem;
      font-weight: 700;
      margin: 0;
    }
  }

  .settings-body {
    @include layout.stack(var(--s-app-space-8));
    max-width: 40rem;
  }

  .settings-section {
    @include layout.stack(var(--s-app-space-3));

    &__title {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      margin: 0;
      text-transform: uppercase;
    }
  }

  .settings-card {
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    overflow: hidden;
  }

  .settings-row {
    @include layout.row(var(--s-app-space-4), center, space-between);
    padding: var(--s-app-space-4);

    & + & {
      border-top: 1px solid var(--s-content-border-color);
    }

    &__info {
      @include layout.row(var(--s-app-space-3), center);
    }

    &__icon {
      color: var(--p-primary-color);
      font-size: 1.1rem;
      width: 1.25rem;
      text-align: center;
    }

    &__label {
      color: var(--s-content-color);
      display: block;
      font-size: 0.95rem;
      font-weight: 500;
    }

    &__hint {
      color: color-mix(in srgb, var(--s-content-color), transparent 45%);
      display: block;
      font-size: 0.8rem;
      margin-top: 0.1rem;
    }
  }
</style>

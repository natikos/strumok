<template>
  <div class="auth-layout">
    <header class="auth-layout__header">
      <img class="auth-layout__logo" src="/logo.svg" alt="Strumok Logo" />

      <div class="auth-layout__controls">
        <LanguageToggleButton class="auth-layout__language-toggle" />

        <ThemeToggleButton class="auth-layout__theme-toggle" />
      </div>
    </header>

    <main class="auth-layout__main">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
  import LanguageToggleButton from "@shared/components/i18n/LanguageToggleButton.vue";
  import ThemeToggleButton from "@shared/components/theme/ThemeToggleButton.vue";
</script>

<style lang="scss" scoped>
  .auth-layout {
    @include layout.stack(0);
    background: linear-gradient(
      to top,
      var(--s-app-background-start) 0%,
      var(--s-app-background-end) 75%
    );
    height: 100dvh;
    min-width: 20rem;
    width: 100%;

    &__header {
      align-items: center;
      display: flex;
      gap: var(--s-app-space-2);
      justify-content: space-between;
      height: auto;
      padding: var(--s-app-space-2) var(--s-app-space-2) 0;
    }

    &__logo {
      display: block;
      max-width: 7.75rem;
      width: 100%;
    }

    &__controls {
      align-items: center;
      display: flex;
      gap: var(--s-app-space-1);
      justify-content: flex-end;
    }

    &__main {
      @include layout.stack(0);
      align-items: start;
      flex: 1;
      justify-content: center;
      margin: 0 auto;
      max-width: 36rem;
      padding: var(--s-app-space-2) var(--s-app-space-2) var(--s-app-space-3);
      width: 100%;
    }

    @media (min-width: 21.25rem) {
      &__logo {
        max-width: 9.5rem;
      }

      &__main {
        padding: var(--s-app-space-3) var(--s-app-space-3) var(--s-app-space-4);
      }
    }

    @media (min-width: 23.125rem) {
      &__header {
        gap: var(--s-app-space-3);
      }

      &__controls {
        gap: var(--s-app-space-2);
      }
    }

    @media (min-width: 48rem) {
      &__header {
        gap: var(--s-app-space-3);
        min-height: 4.5rem;
        padding: var(--s-app-space-4) var(--s-app-space-8) 0;
      }

      &__logo {
        max-width: 12rem;
      }

      &__controls {
        gap: var(--s-app-space-2);
      }

      &__main {
        align-items: center;
        justify-content: center;
        padding: var(--s-app-space-6) var(--s-app-space-6) var(--s-app-space-8);
      }
    }

    @media (min-width: 48rem) and (max-height: 56.25rem) {
      &__main {
        align-items: center;
        justify-content: center;
        padding: var(--s-app-space-3) var(--s-app-space-6) var(--s-app-space-4);
      }
    }
  }

  .dark .auth-layout {
    background: var(--s-app-background);
  }
</style>

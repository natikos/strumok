<template>
  <AuthLayout class="privacy-page">
    <article class="privacy">
      <h1 class="privacy__title">{{ t("privacy.title") }}</h1>
      <p class="privacy__intro">{{ t("privacy.intro") }}</p>

      <section v-for="section in sections" :key="section" class="privacy__section">
        <h2 class="privacy__heading">{{ t(`privacy.sections.${section}.title`) }}</h2>
        <p class="privacy__text">{{ t(`privacy.sections.${section}.body`) }}</p>
      </section>

      <RouterLink class="privacy__back" :to="backTo">{{ t("privacy.back") }}</RouterLink>
    </article>
  </AuthLayout>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import { getAuthSessionState } from "@shared/api/auth-session";
  import { ROUTES } from "@shared/routing/routes";

  const { t } = useI18n();

  const sections = ["collected", "access", "hosting", "retention", "rights"] as const;

  // Reachable signed in or out, so the way back depends on who is reading.
  const backTo = computed(() => (getAuthSessionState().isAuthenticated ? ROUTES.settings : ROUTES.auth));
</script>

<style scoped lang="scss">
  .privacy {
    @include layout.stack(var(--s-app-space-3));
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-lg);
    min-width: 0;
    padding: var(--s-app-space-3);
    width: 100%;

    &__title {
      font-size: 1.5rem;
      margin: 0;
    }

    &__intro,
    &__text {
      color: var(--s-content-secondary-color);
      line-height: 1.5;
      margin: 0;
      overflow-wrap: anywhere;
    }

    &__section {
      @include layout.stack(var(--s-app-space-1));
    }

    &__heading {
      font-size: 1rem;
      margin: 0;
    }

    &__back {
      align-self: flex-start;
      color: var(--p-primary-color);
      font-size: 0.875rem;
    }

    @include layout.respond-to("md") {
      padding: var(--s-app-space-4);
    }
  }
</style>

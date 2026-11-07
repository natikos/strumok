<template>
  <section v-if="isVisible" class="card install" :aria-label="t('install.title')">
    <div class="install__body">
      <h2 class="install__title">{{ t("install.title") }}</h2>
      <p class="install__text">
        {{ showIosSteps ? t("install.ios") : t("install.text") }}
      </p>
    </div>
    <div class="install__actions">
      <Button v-if="canInstall" size="small" :label="t('install.action')" @click="install" />
      <Button
        size="small"
        severity="secondary"
        variant="text"
        :label="t('install.dismiss')"
        @click="dismiss"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";

  import { useInstallPrompt } from "./useInstallPrompt";

  const { t } = useI18n();
  const { canInstall, showIosSteps, isVisible, install, dismiss } = useInstallPrompt();
</script>

<style scoped lang="scss">
  .install {
    border-color: var(--s-primary-100);
    display: grid;
    gap: var(--s-app-space-3);
    min-width: 0;

    &__body {
      min-width: 0;
    }

    &__title {
      color: var(--s-content-color);
      font-size: 1rem;
      font-weight: 700;
      margin: 0;
    }

    &__text {
      color: var(--s-content-secondary-color);
      margin: var(--s-app-space-1) 0 0;
      overflow-wrap: anywhere;
    }

    &__actions {
      display: flex;
      flex-wrap: wrap;
      gap: var(--s-app-space-2);
    }
  }
</style>

<template>
  <Toast position="top-right" />
  <RouterView />
</template>

<script setup lang="ts">
  import Toast from "primevue/toast";
  import { useToast } from "primevue/usetoast";
  import { onBeforeUnmount, onMounted } from "vue";
  import { useI18n } from "vue-i18n";
  import { RouterView } from "vue-router";

  import { useLocale } from "@features/i18n/composables/useLocale";
  import { useTheme } from "@features/theme/composables/useTheme";
  import { registerToastPresenter } from "@shared/api/error-toast";

  const { initializeLocale } = useLocale();
  const { initializeTheme } = useTheme();
  const i18n = useI18n();
  const toast = useToast();

  let unregisterToastPresenter: VoidFunction | null = null;

  initializeLocale();
  initializeTheme();

  onMounted(() => {
    unregisterToastPresenter = registerToastPresenter((payload) => {
      const isTranslationKeyValid = i18n.te(payload.messageKey);

      if (!isTranslationKeyValid && import.meta.env.DEV) {
        throw new Error(
          `Missing i18n key for API toast: "${payload.messageKey}". Add it to locale files.`
        );
      }

      const resolvedMessageKey = isTranslationKeyValid
        ? payload.messageKey
        : payload.fallbackMessageKey;

      const message = i18n.t(resolvedMessageKey);

      toast.add({
        life: payload.life,
        severity: payload.severity,
        summary: message,
      });
    });
  });

  onBeforeUnmount(() => {
    unregisterToastPresenter?.();
  });
</script>

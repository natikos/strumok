<template>
  <div class="settings-page">
    <header class="settings-header">
      <h1 class="settings-header__title">{{ t("settings.title") }}</h1>
    </header>

    <div v-if="me" class="settings-body">
      <section class="settings-section">
        <h2 class="settings-section__title">{{ t("settings.appearance") }}</h2>

        <div class="settings-card">
          <div class="settings-row">
            <div class="settings-row__info">
              <Palette class="settings-row__icon" />
              <div>
                <span class="settings-row__label">{{ t("settings.theme") }}</span>
                <span class="settings-row__hint">{{
                  isDarkTheme ? t("settings.themeDark") : t("settings.themeLight")
                }}</span>
              </div>
            </div>
            <ThemeToggleButton @toggle="handlePreferenceToggle({ theme: $event })" />
          </div>
        </div>
      </section>

      <section class="settings-section">
        <h2 class="settings-section__title">{{ t("settings.account.title") }}</h2>

        <AccountSettings :current-email="me.email" />
      </section>

      <section class="settings-section">
        <h2 class="settings-section__title">{{ t("settings.notifications.title") }}</h2>

        <div class="settings-card">
          <div class="settings-row">
            <div class="settings-row__info">
              <component
                :is="notificationIcon"
                class="settings-row__icon"
                :class="{ 'settings-row__icon--spin': pushState === 'requesting' }"
              />
              <div>
                <span class="settings-row__label">{{ t("settings.notifications.label") }}</span>
                <span
                  class="settings-row__hint"
                  :class="{ 'settings-row__hint--warning': pushState === 'denied' }"
                  >{{ t(`settings.notifications.${pushState}`) }}</span
                >
              </div>
            </div>
            <ToggleSwitch
              v-if="pushState !== 'unsupported'"
              :model-value="pushState === 'on'"
              :disabled="pushState === 'requesting' || pushState === 'denied'"
              @update:model-value="handlePushToggle"
            />
            <span v-else class="settings-row__hint">{{
              t("settings.notifications.unsupported")
            }}</span>
          </div>
        </div>
      </section>

      <RouterLink class="settings-privacy" :to="ROUTES.privacy">
        {{ t("privacy.link") }}
      </RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { Bell, Palette, Spinner } from "@primeicons/vue";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import type { ThemeMode } from "@features/preferences/preferences.storage";
  import { usePushNotifications } from "@features/push-notifications/usePushNotifications";
  import { useTheme } from "@features/theme/composables/useTheme";
  import { getMe, updateMyPreferences, type UserWithHouseholdsOut } from "@shared/api/auth";
  import ThemeToggleButton from "@shared/components/theme/ThemeToggleButton.vue";
  import { ROUTES } from "@shared/routing/routes";

  const { setTheme, isDarkTheme } = useTheme();
  const { state: pushState, enable: enablePush, disable: disablePush } = usePushNotifications();
  const { t } = useI18n();
  const me = ref<UserWithHouseholdsOut | null>(null);

  onMounted(async () => {
    me.value = await getMe();
  });

  const notificationIcon = computed(() => (pushState.value === "requesting" ? Spinner : Bell));

  async function handlePreferenceToggle(payload: {
    theme?: ThemeMode;
  }): Promise<void> {
    try {
      await updateMyPreferences(payload);
    } catch (error) {
      // The toggle already applied the new value locally; undo it if the save failed.
      if (payload.theme) setTheme(payload.theme === "dark" ? "light" : "dark");
      throw error;
    }
  }

  async function handlePushToggle(next: boolean): Promise<void> {
    if (pushState.value === "ios-not-installed") {
      return;
    }

    if (next) {
      await enablePush();
    } else {
      await disablePush();
    }
  }
</script>

<style scoped lang="scss">
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

  .settings-privacy {
    color: var(--p-primary-color);
    font-size: 0.875rem;
    align-self: flex-start;
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
</style>

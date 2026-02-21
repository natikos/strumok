<template>
  <div class="dashboard-page">
    <aside class="dashboard-sidebar">
      <img class="dashboard-sidebar__logo" src="/logo.svg" alt="Strumok Logo" />
      <nav class="dashboard-sidebar__menu" aria-label="Main">
        <button
          v-for="item in sidebarItems"
          :key="item.icon"
          class="dashboard-sidebar__item"
          type="button"
        >
          <i :class="item.icon"></i>
        </button>
      </nav>
    </aside>

    <div class="dashboard-main">
      <header class="dashboard-topbar">
        <p class="dashboard-topbar__hint">Use (cmd + click) on a menu item to open a tab</p>

        <div class="dashboard-topbar__actions">
          <Button
            :label="languageLabel"
            variant="text"
            rounded
            :aria-label="languageAriaLabel"
            :title="languageAriaLabel"
            @click="handleLocaleToggle"
          />
          <Button
            :icon="themeIcon"
            variant="text"
            rounded
            :aria-label="themeAriaLabel"
            :title="themeAriaLabel"
            @click="handleThemeToggle"
          />
          <div class="dashboard-profile">
            <div class="dashboard-profile__avatar">{{ profileInitials }}</div>
            <div class="dashboard-profile__meta">
              <strong>{{ profileName }}</strong>
              <span>{{ t("dashboard.role") }}</span>
            </div>
          </div>
        </div>
      </header>

      <main class="dashboard-content">
        <div class="dashboard-breadcrumb">
          <i class="pi pi-home" aria-hidden="true"></i>
          <span>/</span>
          <span>{{ t("dashboard.title") }}</span>
        </div>

        <section class="dashboard-empty-card" aria-live="polite">
          <h1>{{ welcomeTitle }}</h1>
          <p>{{ welcomeMessage }}</p>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
  import Button from "primevue/button";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { useLocale } from "@features/i18n/composables/useLocale";
  import type { LanguageCode, ThemeMode } from "@features/preferences/preferences.storage";
  import { useTheme } from "@features/theme/composables/useTheme";
  import { getMe, updateMyPreferences } from "@shared/api/auth";
  import type { components } from "@shared/api/generated/openapi";

  type UserOut = components["schemas"]["UserOut"];

  const { t } = useI18n();
  const { currentLocale, setLocale, toggleLocale } = useLocale();
  const { setTheme, theme, toggleTheme } = useTheme();

  const sidebarItems = [
    { icon: "pi pi-home" },
    { icon: "pi pi-th-large" },
    { icon: "pi pi-star" },
    { icon: "pi pi-compass" },
    { icon: "pi pi-briefcase" },
    { icon: "pi pi-wallet" },
    { icon: "pi pi-user" },
    { icon: "pi pi-bars" },
    { icon: "pi pi-download" },
  ];

  const me = ref<UserOut | null>(null);

  onMounted(async () => {
    me.value = await getMe();

    if (me.value.language) {
      setLocale(me.value.language);
    }

    if (me.value.theme) {
      setTheme(me.value.theme);
    }
  });

  async function handleLocaleToggle(): Promise<void> {
    const nextLocale = toggleLocale();
    await savePreferences({ language: nextLocale, theme: theme.value });
  }

  async function handleThemeToggle(): Promise<void> {
    const nextTheme = toggleTheme();
    await savePreferences({ language: currentLocale.value, theme: nextTheme });
  }

  async function savePreferences(payload: { language: LanguageCode; theme: ThemeMode }): Promise<void> {
    try {
      me.value = await updateMyPreferences(payload);
    } catch {
      // API errors are already shown globally by the client middleware.
    }
  }

  const profileName = computed(() => {
    if (!me.value) {
      return t("dashboard.loadingUser");
    }

    return `${me.value.first_name} ${me.value.last_name}`;
  });

  const profileInitials = computed(() => {
    if (!me.value) {
      return "..";
    }

    return `${me.value.first_name[0] ?? ""}${me.value.last_name[0] ?? ""}`.toUpperCase();
  });

  const welcomeTitle = computed(() => {
    if (!me.value) {
      return t("dashboard.loadingTitle");
    }

    return t("dashboard.welcomeTitle", { name: me.value.first_name });
  });

  const welcomeMessage = computed(() => t("dashboard.emptyMessage"));

  const themeIcon = computed(() => (theme.value === "dark" ? "pi pi-moon" : "pi pi-sun"));

  const themeAriaLabel = computed(() =>
    theme.value === "dark" ? t("layout.switchToLightTheme") : t("layout.switchToDarkTheme")
  );

  const languageLabel = computed(() => (currentLocale.value === "ua" ? "UA" : "EN"));

  const languageAriaLabel = computed(() =>
    currentLocale.value === "ua" ? t("layout.switchToEnglish") : t("layout.switchToUkrainian")
  );
</script>

<style scoped lang="scss">
  .dashboard-page {
    background: #edf3f8;
    color: #223142;
    display: grid;
    grid-template-columns: 1fr;
    min-height: 100vh;
  }

  .dashboard-sidebar {
    display: none;
  }

  .dashboard-sidebar__logo {
    aspect-ratio: 1;
    border: 1px solid #d9e3ec;
    border-radius: 999px;
    display: block;
    height: 3rem;
    object-fit: cover;
    width: 3rem;
  }

  .dashboard-sidebar__menu {
    display: flex;
    flex-direction: column;
    gap: var(--s-app-space-2);
    width: 100%;
  }

  .dashboard-sidebar__item {
    align-items: center;
    background: transparent;
    border: 0;
    border-radius: var(--s-app-radius-sm);
    color: #4b6176;
    cursor: pointer;
    display: grid;
    font-size: 1.2rem;
    height: 2.5rem;
    place-items: center;
    transition: background-color 160ms ease;
    width: 100%;
  }

  .dashboard-sidebar__item:hover {
    background: #f2f7fb;
  }

  .dashboard-main {
    display: grid;
    grid-template-rows: auto 1fr;
    min-width: 0;
  }

  .dashboard-topbar {
    align-items: flex-start;
    background: #ffffff;
    border-bottom: 1px solid #d9e3ec;
    display: flex;
    flex-direction: column;
    gap: var(--s-app-space-3);
    min-height: 4rem;
    justify-content: center;
    padding: var(--s-app-space-4);
  }

  .dashboard-topbar__hint {
    color: #627991;
    font-size: var(--s-app-font-size-sm);
    margin: 0;
  }

  .dashboard-topbar__actions {
    align-items: center;
    display: flex;
    gap: var(--s-app-space-2);
    width: 100%;
  }

  .dashboard-profile {
    align-items: center;
    display: flex;
    gap: var(--s-app-space-2);
    margin-left: var(--s-app-space-1);
  }

  .dashboard-profile__avatar {
    align-items: center;
    background: #edf3f8;
    border-radius: 999px;
    color: #31475b;
    display: flex;
    font-size: 0.85rem;
    font-weight: 700;
    height: 2.25rem;
    justify-content: center;
    width: 2.25rem;
  }

  .dashboard-profile__meta {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
  }

  .dashboard-profile__meta strong {
    color: #25384a;
    font-size: 0.95rem;
    font-weight: 600;
  }

  .dashboard-profile__meta span {
    color: #6f8397;
    font-size: 0.8rem;
  }

  .dashboard-content {
    padding: var(--s-app-space-4);
  }

  .dashboard-breadcrumb {
    align-items: center;
    color: #6b8096;
    display: flex;
    font-size: 0.9rem;
    gap: var(--s-app-space-2);
    margin-bottom: var(--s-app-space-4);
  }

  .dashboard-empty-card {
    background: #ffffff;
    border: 1px solid #d9e3ec;
    border-radius: var(--s-app-radius-lg);
    min-height: 14rem;
    padding: var(--s-app-space-6);
  }

  .dashboard-empty-card h1 {
    color: #24374a;
    font-size: 1.7rem;
    margin: 0 0 var(--s-app-space-2);
  }

  .dashboard-empty-card p {
    color: #627991;
    font-size: 1rem;
    margin: 0;
  }

  @media (min-width: 21.25rem) {
    .dashboard-topbar {
      padding: var(--s-app-space-5);
    }

    .dashboard-content {
      padding: var(--s-app-space-5);
    }

    .dashboard-empty-card {
      padding: var(--s-app-space-6);
    }
  }

  @media (min-width: 60rem) {
    .dashboard-page {
      grid-template-columns: 4.75rem 1fr;
    }

    .dashboard-sidebar {
      align-items: center;
      background: #ffffff;
      border-right: 1px solid #d9e3ec;
      display: flex;
      flex-direction: column;
      gap: var(--s-app-space-4);
      padding: var(--s-app-space-3) var(--s-app-space-2);
    }

    .dashboard-topbar {
      align-items: center;
      flex-direction: row;
      justify-content: space-between;
      min-height: 4.1rem;
      padding: 0 var(--s-app-space-5);
    }

    .dashboard-topbar__actions {
      width: auto;
    }

    .dashboard-content {
      padding: var(--s-app-space-5);
    }
  }
</style>

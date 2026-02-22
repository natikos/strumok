<template>
  <div class="dashboard-page">
    <aside class="dashboard-sidebar">
      <img class="dashboard-sidebar__logo" src="/icon.svg" alt="Strumok Icon" />
      <nav class="dashboard-sidebar__menu" aria-label="Main">
        <Button
          v-for="item in sidebarItems"
          :key="item.icon"
          class="dashboard-sidebar__item"
          variant="text"
          rounded
          :aria-label="item.label"
          :title="item.label"
        >
          <i :class="item.icon"></i>
        </Button>
      </nav>
      <Button
        class="dashboard-sidebar__item dashboard-sidebar__logout"
        variant="text"
        rounded
        :aria-label="$t('dashboard.logout')"
        :title="$t('dashboard.logout')"
        :disabled="isLoggingOut"
        @click="handleLogout"
      >
        <i class="pi pi-sign-out"></i>
      </Button>
    </aside>

    <div class="dashboard-main">
      <header class="dashboard-topbar">
        <div class="dashboard-topbar__actions">
          <LanguageToggleButton @toggle="handlePreferenceToggle({ language: $event })" />
          <ThemeToggleButton @toggle="handlePreferenceToggle({ theme: $event })" />
          <div class="dashboard-profile">
            <div class="dashboard-profile__avatar">{{ profileInitials }}</div>
            <div class="dashboard-profile__meta">
              <strong>{{
                me ? `${me.first_name} ${me.last_name}` : $t("dashboard.loadingUser")
              }}</strong>
              <span>{{ $t("dashboard.role") }}</span>
            </div>
          </div>
        </div>
      </header>

      <main class="dashboard-content">
        <div class="dashboard-breadcrumb">
          <i class="pi pi-home" aria-hidden="true"></i>
          <span>/</span>
          <span>{{ $t("dashboard.title") }}</span>
        </div>

        <section class="dashboard-empty-card" aria-live="polite">
          <h1>
            {{
              me
                ? $t("dashboard.welcomeTitle", { name: me.first_name })
                : $t("dashboard.loadingTitle")
            }}
          </h1>
          <p>{{ $t("dashboard.emptyMessage") }}</p>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
  import Button from "primevue/button";
  import { computed, onMounted, ref } from "vue";
  import { useRouter } from "vue-router";

  import { useLocale } from "@features/i18n/composables/useLocale";
  import type { LanguageCode, ThemeMode } from "@features/preferences/preferences.storage";
  import { useTheme } from "@features/theme/composables/useTheme";
  import { getMe, logoutUser, updateMyPreferences } from "@shared/api/auth";
  import type { components } from "@shared/api/generated/openapi";
  import LanguageToggleButton from "@shared/components/i18n/LanguageToggleButton.vue";
  import ThemeToggleButton from "@shared/components/theme/ThemeToggleButton.vue";
  import { ROUTES } from "@shared/routing/routes";

  type UserOut = components["schemas"]["UserOut"];

  const router = useRouter();
  const { setLocale } = useLocale();
  const { setTheme } = useTheme();

  const sidebarItems = [
    { icon: "pi pi-home", label: "Home" },
    { icon: "pi pi-th-large", label: "Apps" },
    { icon: "pi pi-star", label: "Favorites" },
    { icon: "pi pi-compass", label: "Explore" },
    { icon: "pi pi-briefcase", label: "Projects" },
    { icon: "pi pi-wallet", label: "Billing" },
    { icon: "pi pi-user", label: "Profile" },
    { icon: "pi pi-bars", label: "Menu" },
    { icon: "pi pi-download", label: "Downloads" },
  ];

  const me = ref<UserOut | null>(null);
  const isLoggingOut = ref(false);

  onMounted(async () => {
    me.value = await getMe();

    setLocale(me.value.language ?? "ua");
    setTheme(me.value.theme ?? "light");
  });

  async function handlePreferenceToggle(payload: {
    language?: LanguageCode;
    theme?: ThemeMode;
  }): Promise<void> {
    try {
      me.value = await updateMyPreferences(payload);
    } catch {
      // API errors are already shown globally by the client middleware.
    }
  }

  async function handleLogout(): Promise<void> {
    if (isLoggingOut.value) {
      return;
    }

    isLoggingOut.value = true;

    try {
      await logoutUser();
      await router.replace(ROUTES.auth);
    } finally {
      isLoggingOut.value = false;
    }
  }

  const profileInitials = computed(() => {
    if (!me.value) {
      return "..";
    }

    return `${me.value.first_name[0] ?? ""}${me.value.last_name[0] ?? ""}`.toUpperCase();
  });
</script>

<style scoped lang="scss">
  .dashboard-page {
    background: var(--s-content-background);
    color: var(--s-content-color);
    display: grid;
    grid-template-columns: 1fr;
    min-height: 100vh;
  }

  .dashboard-sidebar {
    display: none;

    &__logo {
      display: block;
      height: 3rem;
      width: 3rem;
    }

    &__menu {
      @include layout.stack(var(--s-app-space-2));
      width: 100%;
    }

    &__logout {
      margin-top: auto;
    }

    &__item {
      align-items: center;
      background: transparent;
      border: 0;
      border-radius: var(--s-app-radius-sm);
      color: color-mix(in srgb, var(--s-content-color), transparent 22%);
      cursor: pointer;
      display: grid;
      font-size: 1.2rem;
      height: 2.5rem;
      place-items: center;
      transition: background-color 160ms ease;
      width: 100%;

      &:hover {
        background: var(--s-content-hover-background);
      }
    }
  }

  .dashboard-main {
    display: grid;
    grid-template-rows: auto 1fr;
    min-width: 0;
  }

  .dashboard-topbar {
    @include layout.stack(var(--s-app-space-3));
    align-items: flex-start;
    background: var(--s-content-background);
    min-height: 4rem;
    justify-content: center;
    padding: var(--s-app-space-4);

    &__hint {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: var(--s-app-font-size-sm);
      margin: 0;
    }

    &__actions {
      @include layout.row(var(--s-app-space-2));
      width: 100%;
    }
  }

  .dashboard-profile {
    @include layout.row(var(--s-app-space-2));
    margin-left: var(--s-app-space-1);

    &__avatar {
      background: var(--s-content-hover-background);
      border-radius: 999px;
      color: var(--s-content-color);
      font-size: 0.85rem;
      font-weight: 700;
      @include layout.center-square(2.25rem);
    }

    &__meta {
      @include layout.stack(0);
      line-height: 1.15;

      strong {
        color: var(--s-content-color);
        font-size: 0.95rem;
        font-weight: 600;
      }

      span {
        color: color-mix(in srgb, var(--s-content-color), transparent 35%);
        font-size: 0.8rem;
      }
    }
  }

  .dashboard-content {
    padding: var(--s-app-space-4);
  }

  .dashboard-breadcrumb {
    @include layout.row(var(--s-app-space-2));
    color: color-mix(in srgb, var(--s-content-color), transparent 30%);
    font-size: 0.9rem;
    margin-bottom: var(--s-app-space-4);
  }

  .dashboard-empty-card {
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-lg);
    min-height: 14rem;
    padding: var(--s-app-space-6);
    h1 {
      color: var(--s-content-color);
      font-size: 1.7rem;
      margin: 0 0 var(--s-app-space-2);
    }

    p {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 1rem;
      margin: 0;
    }
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
      @include layout.stack(var(--s-app-space-4));
      align-items: center;
      background: var(--s-content-background);
      padding: var(--s-app-space-3) var(--s-app-space-2);
    }

    .dashboard-topbar {
      @include layout.row(var(--s-app-space-3), center, flex-end);
      min-height: 4.1rem;
      padding: 0 var(--s-app-space-5);
    }

    .dashboard-topbar {
      &__actions {
        width: auto;
      }
    }

    .dashboard-content {
      background: var(--s-app-background);
      border-radius: var(--s-app-radius-lg) 0 0 0;
      box-shadow: inset 0.5px 0.5px 3px 0.5px var(--s-primary-900);
      padding: var(--s-app-space-5);
    }
  }
</style>

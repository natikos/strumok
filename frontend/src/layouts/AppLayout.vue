<template>
  <div class="app-layout">
    <aside class="app-sidebar">
      <img
        class="app-sidebar__logo app-sidebar__logo--icon"
        src="/icon.svg"
        alt="Strumok"
        aria-hidden="true"
      />
      <img class="app-sidebar__logo app-sidebar__logo--wide" src="/logo.svg" alt="Strumok" />
      <nav class="app-sidebar__menu" aria-label="Main">
        <button
          v-for="item in mainItems"
          :key="item.icon"
          class="app-sidebar__item"
          :class="{ 'app-sidebar__item--active': isActiveRoute(item.route) }"
          :aria-label="item.label"
          @click="item.route && router.push(item.route)"
        >
          <i :class="item.icon" aria-hidden="true"></i>
          <span class="app-sidebar__item-label">{{ item.label }}</span>
        </button>
      </nav>
      <div class="app-sidebar__bottom">
        <button
          v-for="item in bottomItems"
          :key="item.icon"
          class="app-sidebar__item"
          :class="{ 'app-sidebar__item--active': isActiveRoute(item.route) }"
          :aria-label="item.label"
          @click="item.route && router.push(item.route)"
        >
          <i :class="item.icon" aria-hidden="true"></i>
          <span class="app-sidebar__item-label">{{ item.label }}</span>
        </button>
        <button
          class="app-sidebar__item"
          :aria-label="$t('nav.logout')"
          :disabled="isLoggingOut"
          @click="handleLogout"
        >
          <i class="pi pi-sign-out" aria-hidden="true"></i>
          <span class="app-sidebar__item-label">{{ $t("nav.logout") }}</span>
        </button>
      </div>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <img class="app-topbar__brand" src="/icon.svg" alt="Strumok" />
        <div class="app-topbar__actions">
          <div v-if="households.length > 1" class="app-household">
            <Select
              :model-value="currentId"
              :options="households"
              option-label="name"
              option-value="id"
              :aria-label="$t('household.switchAria')"
              @update:model-value="onHouseholdChange"
            />
          </div>

          <div class="app-profile">
            <div class="app-profile__avatar">{{ profileInitials }}</div>
            <div class="app-profile__meta">
              <strong>{{
                me ? `${me.first_name} ${me.last_name}` : $t("dashboard.loadingUser")
              }}</strong>
            </div>
          </div>
        </div>
      </header>

      <main class="app-content">
        <RouterView />
      </main>
    </div>

    <nav class="app-mobile-nav" aria-label="Main">
      <button
        v-for="item in [...mainItems, ...bottomItems]"
        :key="item.icon"
        class="app-mobile-nav__item"
        :class="{ 'app-mobile-nav__item--active': isActiveRoute(item.route) }"
        :aria-label="item.label"
        @click="item.route && router.push(item.route)"
      >
        <i :class="item.icon" aria-hidden="true"></i>
        <span class="app-mobile-nav__label">{{ item.label }}</span>
      </button>
      <button
        class="app-mobile-nav__item"
        :aria-label="$t('nav.logout')"
        :disabled="isLoggingOut"
        @click="handleLogout"
      >
        <i class="pi pi-sign-out" aria-hidden="true"></i>
        <span class="app-mobile-nav__label">{{ $t("nav.logout") }}</span>
      </button>
    </nav>
  </div>
</template>

<script setup lang="ts">
  import Select from "primevue/select";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";
  import { RouterView, useRoute, useRouter } from "vue-router";

  import { useCurrentHousehold } from "@features/households/useCurrentHousehold";
  import { useLocale } from "@features/i18n/composables/useLocale";
  import { useTheme } from "@features/theme/composables/useTheme";
  import { getMe, logoutUser } from "@shared/api/auth";
  import type { components } from "@shared/api/generated/openapi";
  import { ROUTES } from "@shared/routing/routes";

  type UserOut = components["schemas"]["UserWithHouseholdsOut"];

  const router = useRouter();
  const route = useRoute();
  const { setLocale } = useLocale();
  const { setTheme } = useTheme();
  const { households, currentId, setHouseholds, setCurrent } = useCurrentHousehold();

  const { t } = useI18n();

  const mainItems = computed(() => [
    { icon: "pi pi-home", label: t("nav.home"), route: ROUTES.root },
    { icon: "pi pi-chart-line", label: t("nav.history"), route: ROUTES.history },
  ]);

  const bottomItems = computed(() => [
    { icon: "pi pi-cog", label: t("nav.settings"), route: ROUTES.settings },
  ]);

  const me = ref<UserOut | null>(null);
  const isLoggingOut = ref(false);

  onMounted(async () => {
    me.value = await getMe();
    setLocale(me.value.language);
    setTheme(me.value.theme);
    setHouseholds(me.value.households);
  });

  function onHouseholdChange(value: number): void {
    setCurrent(value);
  }

  function isActiveRoute(routePath: string | undefined): boolean {
    return !!routePath && route.path === routePath;
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
  .app-layout {
    background: var(--s-shell-background);
    color: var(--s-content-color);
    display: grid;
    grid-template-columns: 1fr;
    height: 100dvh;
    overflow: hidden;
    padding-bottom: 4rem;
  }

  .app-sidebar {
    display: none;

    &__logo {
      display: block;
      margin-bottom: var(--s-app-space-2);

      &--icon {
        height: 2.5rem;
        width: 2.5rem;
      }

      &--wide {
        display: none;
        width: 100%;
        height: auto;
      }
    }

    &__menu {
      @include layout.stack(var(--s-app-space-1));
      width: 100%;
    }

    &__bottom {
      @include layout.stack(var(--s-app-space-1));
      margin-top: auto;
      width: 100%;
    }

    &__item {
      align-items: center;
      background: transparent;
      border: 0;
      border-radius: var(--s-app-radius-sm);
      color: color-mix(in srgb, var(--s-content-color), transparent 30%);
      cursor: pointer;
      display: flex;
      flex-direction: row;
      gap: var(--s-app-space-3);
      font-size: 1rem;
      min-height: 2.75rem;
      padding: 0 var(--s-app-space-3);
      transition:
        background-color 160ms ease,
        color 160ms ease;
      width: 100%;
      text-align: left;

      &:hover {
        background: var(--s-content-hover-background);
        color: var(--s-content-color);
      }

      &--active {
        background: var(--s-shell-item-active-background);
        color: var(--s-content-color);
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      i {
        font-size: 1.05rem;
        flex-shrink: 0;
        width: 1.25rem;
        text-align: center;
      }
    }

    &__item-label {
      font-size: 0.9rem;
      font-weight: 500;
    }
  }

  .app-main {
    display: grid;
    grid-template-rows: auto 1fr;
    min-height: 0;
    min-width: 0;
  }

  .app-topbar {
    align-items: center;
    background: transparent;
    display: flex;
    flex-direction: row;
    gap: var(--s-app-space-2);
    min-height: 4rem;
    padding: var(--s-app-space-3) var(--s-app-space-4);

    &__actions {
      @include layout.row(var(--s-app-space-2));
      margin-left: auto;
    }
  }

  .app-topbar__brand {
    height: 2.5rem;
    width: 2.5rem;

    @media (min-width: 60rem) {
      display: none;
    }
  }

  .app-household {
    @include layout.row(var(--s-app-space-2));
    margin-left: auto;
  }

  .app-profile {
    @include layout.row(var(--s-app-space-2));
    margin-left: auto;

    .app-household + & {
      margin-left: 0;
    }

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

  .app-content {
    min-height: 0;
    overflow-y: auto;
    padding: var(--s-app-space-5);
  }

  @media (min-width: 21.25rem) {
    .app-topbar {
      padding: var(--s-app-space-5);
    }
  }

  .app-mobile-nav {
    @include layout.row(0);
    background: var(--s-shell-background);
    border-top: 1px solid color-mix(in srgb, var(--s-content-color), transparent 88%);
    bottom: 0;
    left: 0;
    position: fixed;
    right: 0;
    z-index: 100;

    &__item {
      align-items: center;
      background: transparent;
      border: 0;
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      cursor: pointer;
      display: flex;
      flex-direction: column;
      flex: 1;
      font-size: 1.1rem;
      gap: 0.2rem;
      height: 4rem;
      justify-content: center;
      padding: 0;
      transition: color 160ms ease;

      &:hover,
      &--active {
        color: var(--s-content-color);
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }

    &__label {
      font-size: 0.65rem;
      font-weight: 600;
      letter-spacing: 0.02em;
    }
  }

  @media (min-width: 60rem) {
    .app-layout {
      grid-template-columns: 13rem 1fr;
      padding-bottom: 0;
    }

    .app-mobile-nav {
      display: none;
    }

    .app-sidebar {
      @include layout.stack(var(--s-app-space-1));
      align-items: flex-start;
      background: transparent;
      padding: var(--s-app-space-4) var(--s-app-space-3);

      &__logo--icon {
        display: none;
      }
      &__logo--wide {
        display: block;
      }
    }

    .app-topbar {
      min-height: 4.1rem;
      padding: 0 var(--s-app-space-5);
    }

    .app-content {
      padding: var(--s-app-space-8);
      background: var(--s-app-background);
      border-radius: var(--s-app-radius-lg) 0 0 0;
      box-shadow: inset 0.5px 0.5px 3px 0.5px var(--s-content-inset-shadow-color);
    }
  }
</style>

<template>
  <div class="demo-page">
    <aside class="demo-sidebar">
      <img class="demo-sidebar__logo" src="/logo.svg" alt="Strumok Logo" />
      <nav class="demo-sidebar__menu" aria-label="Main">
        <button
          v-for="item in sidebarItems"
          :key="item.icon"
          class="demo-sidebar__item"
          type="button"
        >
          <i :class="item.icon"></i>
        </button>
      </nav>
    </aside>

    <div class="demo-main">
      <header class="demo-topbar">
        <p class="demo-topbar__hint">Use (cmd + click) on a menu item to open a tab</p>
        <div class="demo-topbar__actions">
          <Button
            :label="languageLabel"
            variant="text"
            rounded
            :aria-label="languageAriaLabel"
            :title="languageAriaLabel"
            @click="toggleLocale"
          />
          <Button
            :icon="themeIcon"
            variant="text"
            rounded
            :aria-label="themeAriaLabel"
            :title="themeAriaLabel"
            @click="toggleTheme"
          />
          <div class="demo-profile">
            <div class="demo-profile__avatar">GR</div>
            <div class="demo-profile__meta">
              <strong>Gene Russell</strong>
              <span>Developer</span>
            </div>
          </div>
        </div>
      </header>

      <main class="demo-content">
        <div class="demo-breadcrumb">
          <i class="pi pi-home"></i><span>/</span><span>SaaS Dashboard</span>
        </div>

        <section class="demo-kpis">
          <article
            v-for="kpi in kpis"
            :key="kpi.label"
            class="demo-kpi"
            :style="{ '--kpi-color': kpi.color }"
          >
            <i :class="kpi.icon"></i>
            <p>{{ kpi.label }}</p>
            <strong>{{ kpi.value }}</strong>
            <div class="demo-kpi__wave"></div>
          </article>
        </section>

        <section class="demo-panels">
          <article class="demo-panel demo-panel--chart">
            <header>
              <h2>Acquisition Overview</h2>
              <button type="button">Last Week</button>
            </header>
            <div class="demo-chart">
              <div v-for="(item, idx) in chartBars" :key="idx" class="demo-chart__item">
                <div class="demo-chart__bar" :style="{ height: item + '%' }"></div>
              </div>
              <svg
                class="demo-chart__line"
                viewBox="0 0 100 35"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <polyline points="0,10 15,18 30,22 45,20 60,21 75,13 90,15 100,16" />
              </svg>
            </div>
          </article>

          <article class="demo-panel">
            <h2>Latest Customers</h2>
            <ul class="demo-customers">
              <li v-for="customer in customers" :key="customer.name">
                <span class="demo-customers__avatar">{{ customer.initials }}</span>
                <div>
                  <strong>{{ customer.name }}</strong>
                  <p>{{ customer.role }}</p>
                </div>
              </li>
            </ul>
            <Button class="demo-customers__cta" label="View All" />
          </article>

          <article class="demo-panel demo-panel--gauge">
            <div class="demo-gauge">
              <div class="demo-gauge__arc"></div>
              <div class="demo-gauge__value">32.79%</div>
            </div>
            <ul class="demo-tasks">
              <li v-for="task in tasks" :key="task.title">
                <strong>{{ task.title }}</strong>
                <p>{{ task.action }}</p>
              </li>
            </ul>
          </article>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
  import Button from "primevue/button";
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import { useLocale } from "@features/i18n/composables/useLocale";
  import { useTheme } from "@features/theme/composables/useTheme";

  const { t } = useI18n();
  const { currentLocale, toggleLocale } = useLocale();
  const { theme, toggleTheme } = useTheme();

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

  const kpis = [
    { color: "#2eb9ff", icon: "pi pi-users", label: "USERS SIGNED UP", value: "3882" },
    { color: "#f9ae3e", icon: "pi pi-map", label: "LIFETIME VALUE", value: "532" },
    { color: "#29dc96", icon: "pi pi-percentage", label: "CONVERSION RATE", value: "12.6%" },
    { color: "#aa60ff", icon: "pi pi-comment", label: "ACTIVE TRIALS", value: "440" },
  ];

  const chartBars = [62, 38, 80, 56, 30, 65, 52];

  const customers = [
    { initials: "BS", name: "Brooklyn Simmons", role: "Manager at Mitsubishi" },
    { initials: "LA", name: "Leslie Alexander", role: "Customer Success at General Electric" },
    { initials: "JB", name: "Jerome Bell", role: "Mario Carrier at Nintendo" },
    { initials: "JJ", name: "Jim Jones", role: "Reliability Engineer at eBay" },
    { initials: "AB", name: "Annette Black", role: "Delivery Woman at Pizza Hut" },
    { initials: "AF", name: "Albert Flores", role: "Team Leader at Insomniac Games" },
  ];

  const tasks = [
    { action: "Go Profile Edit", title: "Add your personal information" },
    { action: "Send Verification SMS", title: "Verify your phone" },
    { action: "Upload Pictures", title: "Verify your Face ID" },
    { action: "View Agreement", title: "Give permissions for personal data" },
  ];

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
  .demo-page {
    background: linear-gradient(180deg, #131a2b 0%, #0e1422 100%);
    color: var(--s-text-color);
    display: grid;
    grid-template-columns: 4.75rem 1fr;
    min-height: 100vh;
  }

  .demo-sidebar {
    background: color-mix(in srgb, var(--s-surface-0), #122033 25%);
    border-right: 1px solid color-mix(in srgb, var(--s-surface-300), transparent 40%);
    padding: var(--s-app-space-4) var(--s-app-space-3);
  }

  .demo-sidebar__logo {
    aspect-ratio: 1;
    border: 2px solid color-mix(in srgb, var(--s-surface-800), #fff 40%);
    border-radius: 50%;
    display: block;
    margin: 0 auto var(--s-app-space-6);
    max-width: 2.9rem;
    object-fit: cover;
  }

  .demo-sidebar__menu {
    display: flex;
    flex-direction: column;
    gap: var(--s-app-space-2);
  }

  .demo-sidebar__item {
    align-items: center;
    background: transparent;
    border: 0;
    border-radius: var(--s-app-radius-md);
    color: color-mix(in srgb, var(--s-text-color), white 25%);
    cursor: pointer;
    display: grid;
    height: 2.5rem;
    place-items: center;
    transition: background-color 180ms ease;
    width: 2.5rem;
  }

  .demo-sidebar__item:hover {
    background: color-mix(in srgb, var(--s-primary-color), transparent 78%);
  }

  .demo-main {
    display: grid;
    grid-template-rows: auto 1fr;
    min-width: 0;
  }

  .demo-topbar {
    align-items: center;
    display: flex;
    justify-content: space-between;
    padding: var(--s-app-space-4) var(--s-app-space-6);
  }

  .demo-topbar__hint {
    color: color-mix(in srgb, var(--s-text-color), white 20%);
    font-size: var(--s-app-font-size-sm);
    margin: 0;
  }

  .demo-topbar__actions {
    align-items: center;
    display: flex;
    gap: var(--s-app-space-3);
  }

  .demo-profile {
    align-items: center;
    display: flex;
    gap: var(--s-app-space-2);
  }

  .demo-profile__avatar {
    align-items: center;
    background: linear-gradient(135deg, #6bd0ff, #2b5cc8);
    border-radius: 50%;
    color: #f8fdff;
    display: grid;
    font-size: var(--s-app-font-size-sm);
    font-weight: 700;
    height: 2.25rem;
    justify-content: center;
    width: 2.25rem;
  }

  .demo-profile__meta {
    display: grid;
    line-height: 1.25;
  }

  .demo-profile__meta strong {
    font-size: var(--s-app-font-size-sm);
  }

  .demo-profile__meta span {
    color: var(--s-text-muted-color);
    font-size: var(--s-app-font-size-xs);
  }

  .demo-content {
    background: color-mix(in srgb, var(--s-surface-0), #122033 22%);
    border-radius: var(--s-app-radius-lg);
    margin: 0 var(--s-app-space-4) var(--s-app-space-4);
    padding: var(--s-app-space-5);
  }

  .demo-breadcrumb {
    align-items: center;
    color: var(--s-text-muted-color);
    display: flex;
    gap: var(--s-app-space-2);
    margin-bottom: var(--s-app-space-4);
  }

  .demo-kpis {
    display: grid;
    gap: var(--s-app-space-4);
    grid-template-columns: repeat(4, minmax(0, 1fr));
    margin-bottom: var(--s-app-space-4);
  }

  .demo-kpi {
    background: color-mix(in srgb, var(--s-surface-100), #1b2537 30%);
    border-radius: var(--s-app-radius-md);
    overflow: hidden;
    padding: var(--s-app-space-4);
    position: relative;
  }

  .demo-kpi i,
  .demo-kpi p,
  .demo-kpi strong {
    color: var(--kpi-color);
    position: relative;
    z-index: 1;
  }

  .demo-kpi i {
    font-size: 1.75rem;
  }

  .demo-kpi p {
    font-size: var(--s-app-font-size-sm);
    margin: var(--s-app-space-2) 0 var(--s-app-space-1);
  }

  .demo-kpi strong {
    font-size: 2rem;
    line-height: 1;
  }

  .demo-kpi__wave {
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--kpi-color), transparent 76%),
      transparent
    );
    border-radius: 999px;
    bottom: -1.5rem;
    height: 3.5rem;
    left: -10%;
    position: absolute;
    width: 120%;
  }

  .demo-panels {
    display: grid;
    gap: var(--s-app-space-4);
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(16rem, 0.95fr);
  }

  .demo-panel {
    background: color-mix(in srgb, var(--s-surface-100), #1b2537 28%);
    border-radius: var(--s-app-radius-md);
    padding: var(--s-app-space-4);
  }

  .demo-panel h2 {
    font-size: var(--s-app-font-size-lg);
    margin: 0 0 var(--s-app-space-4);
  }

  .demo-panel--chart header {
    align-items: center;
    display: grid;
    gap: var(--s-app-space-3);
    grid-template-columns: 1fr auto;
  }

  .demo-panel--chart button {
    background: transparent;
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-sm);
    color: var(--s-text-color);
    font: inherit;
    padding: 0.45rem 0.75rem;
  }

  .demo-chart {
    align-items: end;
    display: grid;
    gap: var(--s-app-space-4);
    grid-template-columns: repeat(7, 1fr);
    height: 18rem;
    margin-top: var(--s-app-space-4);
    padding: 0 var(--s-app-space-3) var(--s-app-space-2);
    position: relative;
  }

  .demo-chart__item {
    align-items: end;
    display: grid;
    height: 100%;
  }

  .demo-chart__bar {
    background: color-mix(in srgb, var(--s-surface-800), #e5eef8 22%);
    border-radius: 999px;
    opacity: 0.9;
  }

  .demo-chart__line {
    bottom: var(--s-app-space-2);
    height: 5.5rem;
    left: var(--s-app-space-3);
    position: absolute;
    width: calc(100% - 1.5rem);
  }

  .demo-chart__line polyline {
    fill: none;
    stroke: color-mix(in srgb, var(--s-primary-color), #9ed7ee 30%);
    stroke-width: 2;
  }

  .demo-customers {
    display: grid;
    gap: var(--s-app-space-3);
    list-style: none;
    margin: 0 0 var(--s-app-space-4);
    padding: 0;
  }

  .demo-customers li {
    align-items: center;
    display: flex;
    gap: var(--s-app-space-2);
  }

  .demo-customers__avatar {
    align-items: center;
    border: 1px solid color-mix(in srgb, var(--s-primary-color), transparent 35%);
    border-radius: 50%;
    color: var(--s-primary-color);
    display: grid;
    font-size: var(--s-app-font-size-sm);
    height: 2.4rem;
    justify-content: center;
    width: 2.4rem;
  }

  .demo-customers strong {
    font-size: var(--s-app-font-size-sm);
  }

  .demo-customers p {
    color: var(--s-text-muted-color);
    font-size: var(--s-app-font-size-xs);
    margin: 0.2rem 0 0;
  }

  .demo-customers__cta {
    width: 100%;
  }

  .demo-gauge {
    margin: 0 auto var(--s-app-space-4);
    max-width: 13rem;
    position: relative;
  }

  .demo-gauge__arc {
    background: conic-gradient(from 180deg, #79ccb0 32.79%, #7f8ea3 0);
    border-radius: 13rem 13rem 0 0;
    height: 6.2rem;
    overflow: hidden;
    position: relative;
  }

  .demo-gauge__arc::after {
    background: color-mix(in srgb, var(--s-surface-100), #1b2537 28%);
    border-radius: 10rem 10rem 0 0;
    content: "";
    height: 4.6rem;
    inset: 1.15rem 1.15rem 0;
    position: absolute;
  }

  .demo-gauge__value {
    font-size: 2rem;
    font-weight: 600;
    left: 50%;
    position: absolute;
    top: 55%;
    transform: translate(-50%, -50%);
  }

  .demo-tasks {
    display: grid;
    gap: var(--s-app-space-3);
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .demo-tasks p {
    color: var(--s-primary-color);
    font-size: var(--s-app-font-size-sm);
    margin: var(--s-app-space-1) 0 0;
  }

  @media (max-width: 1100px) {
    .demo-kpis {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .demo-panels {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 760px) {
    .demo-page {
      grid-template-columns: 1fr;
    }

    .demo-sidebar {
      border-bottom: 1px solid color-mix(in srgb, var(--s-surface-300), transparent 40%);
      border-right: 0;
      padding-bottom: var(--s-app-space-3);
    }

    .demo-sidebar__menu {
      flex-direction: row;
      flex-wrap: wrap;
      justify-content: center;
    }

    .demo-topbar {
      align-items: flex-start;
      display: flex;
      flex-direction: column;
      gap: var(--s-app-space-3);
    }
  }
</style>

import "primeicons/primeicons.css";
import PrimeVue from "primevue/config";
import ToastService from "primevue/toastservice";
import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";

import { i18n } from "@features/i18n";
import AuthPage from "@pages/auth/AuthPage.vue";
import DashboardPage from "@pages/dashboard/DashboardPage.vue";
import { isAuthenticated } from "@shared/api/auth-session";
import { ROUTES } from "@shared/routing/routes";

import App from "./App.vue";
import AppPreset from "./preset";
import "./style.scss";

const app = createApp(App);

const routes = [
  { component: DashboardPage, meta: { authRequired: true }, path: ROUTES.dashboard },
  { component: AuthPage, meta: { guestOnly: true }, path: ROUTES.auth },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  if (to.meta["guestOnly"]) {
    return (await isAuthenticated()) ? ROUTES.dashboard : true;
  }

  if (to.meta["authRequired"]) {
    return (await isAuthenticated()) ? true : ROUTES.auth;
  }

  return true;
});

app
  .use(i18n)
  .use(router)
  .use(PrimeVue, {
    theme: {
      options: {
        darkModeSelector: ".dark",
        prefix: "s",
      },
      preset: AppPreset,
    },
  })
  .use(ToastService);

app.mount("#app");

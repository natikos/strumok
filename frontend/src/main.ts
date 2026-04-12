import "primeicons/primeicons.css";
import PrimeVue from "primevue/config";
import ToastService from "primevue/toastservice";
import { createApp } from "vue";
import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import { i18n } from "@features/i18n";
import AuthPage from "@pages/auth/AuthPage.vue";
import VerifyEmailPage from "@pages/auth/VerifyEmailPage.vue";
import DashboardPage from "@pages/dashboard/DashboardPage.vue";
import { getAuthSessionState, initAuthSession } from "@shared/api/auth-session";
import { ROUTES } from "@shared/routing/routes";

import App from "./App.vue";
import AppPreset from "./preset";
import "./style.scss";

const app = createApp(App);

const routes: RouteRecordRaw[] = [
  { component: DashboardPage, meta: { authRequired: true }, path: ROUTES.dashboard },
  { component: AuthPage, meta: { guestOnly: true }, path: ROUTES.auth },
  { component: VerifyEmailPage, meta: { authRequired: true }, path: ROUTES.verifyEmail },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

const authReady = initAuthSession();

router.beforeEach(async (to) => {
  await authReady;

  const { isAuthenticated, isEmailVerified } = getAuthSessionState();
  const isGoingToVerify = to.path === ROUTES.verifyEmail;

  if (to.meta["guestOnly"]) {
    if (!isAuthenticated) {
      return true;
    }

    return isEmailVerified ? ROUTES.dashboard : ROUTES.verifyEmail;
  }

  if (to.meta["authRequired"]) {
    if (!isAuthenticated) {
      return ROUTES.auth;
    }

    if (!isEmailVerified && !isGoingToVerify) {
      return ROUTES.verifyEmail;
    }

    if (isEmailVerified && isGoingToVerify) {
      return ROUTES.dashboard;
    }

    return true;
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

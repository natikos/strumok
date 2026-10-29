import PrimeVue from "primevue/config";
import ConfirmationService from "primevue/confirmationservice";
import ToastService from "primevue/toastservice";
import { registerSW } from "virtual:pwa-register";
import { createApp } from "vue";
import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import { i18n } from "@features/i18n";
import {
  getAuthSessionState,
  initAuthSession,
  setAuthSessionState,
} from "@shared/api/auth-session";
import { registerSessionExpiredHandler } from "@shared/api/client";
import { ROUTES } from "@shared/routing/routes";

import App from "./App.vue";
import AppPreset from "./preset";
import "./style.scss";

const app = createApp(App);

registerSW();

const routes: RouteRecordRaw[] = [
  {
    component: () => import("@/layouts/AppLayout.vue"),
    meta: { authRequired: true },
    path: ROUTES.root,
    children: [
      { component: () => import("@pages/dashboard/DashboardPage.vue"), path: "" },
      { component: () => import("@pages/history/UsageHistoryPage.vue"), path: ROUTES.history },
      { component: () => import("@pages/settings/SettingsPage.vue"), path: ROUTES.settings },
      { component: () => import("@pages/admin/AdminPage.vue"), path: ROUTES.admin },
    ],
  },
  {
    component: () => import("@pages/auth/AuthPage.vue"),
    meta: { guestOnly: true },
    path: ROUTES.auth,
  },
  {
    component: () => import("@pages/auth/ForgotPasswordPage.vue"),
    meta: { guestOnly: true },
    path: ROUTES.forgotPassword,
  },
  {
    component: () => import("@pages/auth/PrivacyPage.vue"),
    path: ROUTES.privacy,
  },
  {
    component: () => import("@pages/auth/ResetPasswordPage.vue"),
    path: ROUTES.resetPassword,
  },
  {
    component: () => import("@pages/auth/SetPasswordPage.vue"),
    path: ROUTES.setPassword,
  },
  {
    component: () => import("@pages/auth/ConfirmEmailChangePage.vue"),
    path: ROUTES.confirmEmailChange,
  },
  {
    component: () => import("@pages/auth/VerifyEmailPage.vue"),
    meta: { authRequired: true },
    path: ROUTES.verifyEmail,
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

const authReady = initAuthSession();

// A failed login also 401s with a rejected refresh; only a signed-in session
// is cleared and sent to login.
registerSessionExpiredHandler(() => {
  if (!getAuthSessionState().isAuthenticated) {
    return false;
  }

  setAuthSessionState(false, false);
  void router.replace(ROUTES.auth);
  return true;
});

router.beforeEach(async (to) => {
  await authReady;

  const { isAuthenticated, isEmailVerified } = getAuthSessionState();
  const isGoingToVerify = to.path === ROUTES.verifyEmail;

  if (isGoingToVerify && typeof to.query["token"] === "string") {
    return true;
  }

  if (to.meta["guestOnly"]) {
    if (!isAuthenticated) {
      return true;
    }

    return isEmailVerified ? ROUTES.root : ROUTES.verifyEmail;
  }

  if (to.meta["authRequired"]) {
    if (!isAuthenticated) {
      return ROUTES.auth;
    }

    if (!isEmailVerified && !isGoingToVerify) {
      return ROUTES.verifyEmail;
    }

    if (isEmailVerified && isGoingToVerify) {
      return ROUTES.root;
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
  .use(ToastService)
  .use(ConfirmationService);

app.mount("#app");

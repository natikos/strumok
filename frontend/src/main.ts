import "primeicons/primeicons.css";
import PrimeVue from "primevue/config";
import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";

import { i18n } from "@features/i18n";
import AuthPage from "@pages/auth/AuthPage.vue";
import DemoPage from "@pages/demo/DemoPage.vue";

import App from "./App.vue";
import AppPreset from "./preset";
import "./style.scss";

const app = createApp(App);

app.use(PrimeVue, {
  theme: {
    options: {
      darkModeSelector: ".dark",
      prefix: "s",
    },
    preset: AppPreset,
  },
});

const routes = [
  { component: AuthPage, path: "/" },
  { component: DemoPage, path: "/demo" },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

app.use(i18n).use(router);

app.mount("#app");

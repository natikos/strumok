import { definePreset } from "@primeuix/themes";
import Aura from "@primeuix/themes/aura";
import "primeicons/primeicons.css";
import PrimeVue from "primevue/config";
import { createApp } from "vue";

import App from "./App.vue";
import "./style.css";

const AppPreset = definePreset(Aura, {
  colorScheme: {
    dark: {
      surface: {
        0: "#0b1220",
        50: "#111827",
        100: "#1f2937",
        200: "#273549",
        300: "#334155",
        400: "#475569",
        500: "#64748b",
        600: "#94a3b8",
        700: "#cbd5e1",
        800: "#e2e8f0",
        900: "#f1f5f9",
        950: "#f8fafc",
      },
    },
    light: {
      surface: {
        0: "#ffffff",
        50: "#f8fafc",
        100: "#f1f5f9",
        200: "#e2e8f0",
        300: "#cbd5e1",
        400: "#94a3b8",
        500: "#64748b",
        600: "#475569",
        700: "#334155",
        800: "#1e293b",
        900: "#0f172a",
        950: "#020617",
      },
    },
  },
  semantic: {
    primary: {
      50: "#eff6ff",
      100: "#dbeafe",
      200: "#bfdbfe",
      300: "#93c5fd",
      400: "#60a5fa",
      500: "#3b82f6",
      600: "#2563eb",
      700: "#1d4ed8",
      800: "#1e40af",
      900: "#1e3a8a",
      950: "#172554",
    },
  },
});

const app = createApp(App);

app.use(PrimeVue, {
  theme: {
    options: {
      darkModeSelector: ".app-dark",
    },
    preset: AppPreset,
  },
});

app.mount("#app");

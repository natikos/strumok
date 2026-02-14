import "primeicons/primeicons.css";
import PrimeVue from "primevue/config";
import { createApp } from "vue";

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

app.mount("#app");

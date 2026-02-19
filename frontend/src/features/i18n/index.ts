import { createI18n } from "vue-i18n";

import en from "./locales/en.json";
import ua from "./locales/ua.json";

export const i18n = createI18n({
  fallbackLocale: "en",
  legacy: false,
  locale: "ua",
  messages: {
    en,
    ua,
  },
});

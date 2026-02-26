import { createI18n } from "vue-i18n";

import { getStoredLanguage } from "@features/preferences/preferences.storage";

import en from "./locales/en.json";
import ua from "./locales/ua.json";

export const i18n = createI18n({
  fallbackLocale: "en",
  legacy: false,
  locale: getStoredLanguage(),
  messages: {
    en,
    ua,
  },
});

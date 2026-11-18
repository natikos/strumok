import { createI18n } from "vue-i18n";

import ua from "./locales/ua.json";

export const i18n = createI18n({
  fallbackLocale: "ua",
  legacy: false,
  locale: "ua",
  messages: { ua },
});

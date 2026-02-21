import { computed } from "vue";
import { useI18n } from "vue-i18n";

import {
  getLanguagePreference,
  type LanguageCode,
  setLanguagePreference,
} from "@/features/preferences/preferences.storage";

const SUPPORTED_LOCALES: readonly LanguageCode[] = ["en", "ua"];

export function useLocale() {
  const { locale } = useI18n();

  const initializeLocale = (): void => {
    const savedLocale = getLanguagePreference();

    if (savedLocale) {
      locale.value = savedLocale;
      return;
    }

    const browserLocale = navigator.language.toLowerCase();
    locale.value = browserLocale.startsWith("uk") ? "ua" : "en";
  };

  const setLocale = (value: LanguageCode): void => {
    if (!SUPPORTED_LOCALES.includes(value)) {
      return;
    }

    locale.value = value;
    setLanguagePreference(value);
  };

  const toggleLocale = (): void => {
    const nextLocale: LanguageCode = locale.value === "ua" ? "en" : "ua";
    setLocale(nextLocale);
  };

  return {
    currentLocale: computed(() => locale.value === "ua" ? "ua" : "en"),
    initializeLocale,
    setLocale,
    toggleLocale,
  };
}

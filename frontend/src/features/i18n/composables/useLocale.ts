import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { LanguageCode } from "@/features/preferences/preferences.storage";

const SUPPORTED_LOCALES: readonly LanguageCode[] = ["en", "ua"];

export function useLocale() {
  const { locale } = useI18n();

  const initializeLocale = (): void => {
    const browserLocale = navigator.language.toLowerCase();
    locale.value = browserLocale.startsWith("uk") ? "ua" : "en";
  };

  const setLocale = (value: LanguageCode): void => {
    if (!SUPPORTED_LOCALES.includes(value)) {
      return;
    }

    locale.value = value;
  };

  const toggleLocale = (): LanguageCode => {
    const nextLocale: LanguageCode = locale.value === "ua" ? "en" : "ua";
    setLocale(nextLocale);
    return nextLocale;
  };

  return {
    currentLocale: computed(() => locale.value === "ua" ? "ua" : "en"),
    initializeLocale,
    setLocale,
    toggleLocale,
  };
}

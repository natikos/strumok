import { computed } from "vue";
import { useI18n } from "vue-i18n";

import {
  getStoredLanguage,
  type LanguageCode,
  storeLanguage,
} from "@/features/preferences/preferences.storage";

const SUPPORTED_LOCALES: readonly LanguageCode[] = ["en", "ua"];

export function useLocale() {
  const { locale } = useI18n();

  const initializeLocale = (): void => {
    setLocale(getStoredLanguage());
  };

  const setLocale = (value: LanguageCode): void => {
    if (!SUPPORTED_LOCALES.includes(value)) {
      return;
    }

    locale.value = value;
    storeLanguage(value);
  };

  const toggleLocale = (): LanguageCode => {
    const nextLocale: LanguageCode = locale.value === "en" ? "ua" : "en";
    setLocale(nextLocale);
    return nextLocale;
  };

  return {
    currentLocale: computed(() => (locale.value === "ua" ? "ua" : "en") as LanguageCode),
    initializeLocale,
    setLocale,
    toggleLocale,
  };
}

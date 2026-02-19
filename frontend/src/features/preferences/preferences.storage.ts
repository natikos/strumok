export type ThemeMode = "light" | "dark";
export type LanguageCode = "en" | "ua";

const THEME_STORAGE_KEY = "strumok-theme";
const LANGUAGE_STORAGE_KEY = "strumok-language";

export function getThemePreference(): ThemeMode | null {
  return localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null;
}

export function setThemePreference(theme: ThemeMode): void {
  localStorage.setItem(THEME_STORAGE_KEY, theme);
}

export function getLanguagePreference(): LanguageCode | null {
  return localStorage.getItem(LANGUAGE_STORAGE_KEY) as LanguageCode | null;
}

export function setLanguagePreference(language: LanguageCode): void {
  localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
}

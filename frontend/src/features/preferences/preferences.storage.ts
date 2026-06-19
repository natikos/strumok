import type { components } from "@shared/api/generated/openapi";

type UserPreferencesIn = components["schemas"]["UserPreferencesIn"];

export type ThemeMode = NonNullable<UserPreferencesIn["theme"]>;
export type LanguageCode = NonNullable<UserPreferencesIn["language"]>;

const STORAGE_KEY = "strumok:user-preferences";

interface StoredPreferences {
  language?: LanguageCode;
  theme?: ThemeMode;
}

const DEFAULT_PREFERENCES: Required<StoredPreferences> = {
  language: "ua",
  theme: "light",
};

function readStoredPreferences(): StoredPreferences {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredPreferences) : {};
  } catch {
    return {};
  }
}

function writeStoredPreferences(next: StoredPreferences): void {
  try {
    const merged = { ...readStoredPreferences(), ...next };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  } catch {
    // Ignore storage failures.
  }
}

export function getStoredTheme(): ThemeMode {
  const { theme } = readStoredPreferences();

  if (theme === "light" || theme === "dark") {
    return theme;
  }

  writeStoredPreferences({ theme: DEFAULT_PREFERENCES.theme });
  return DEFAULT_PREFERENCES.theme;
}

export function getStoredLanguage(): LanguageCode {
  const { language } = readStoredPreferences();

  if (language === "ua" || language === "en") {
    return language;
  }

  writeStoredPreferences({ language: DEFAULT_PREFERENCES.language });
  return DEFAULT_PREFERENCES.language;
}

export function storeTheme(theme: ThemeMode): void {
  writeStoredPreferences({ theme });
}

export function storeLanguage(language: LanguageCode): void {
  writeStoredPreferences({ language });
}

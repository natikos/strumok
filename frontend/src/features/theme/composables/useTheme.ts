import { ref } from "vue";

import {
  getThemePreference,
  setThemePreference,
  type ThemeMode,
} from "@/features/preferences/preferences.storage";

const theme = ref<ThemeMode>("light");

function applyTheme(value: ThemeMode): void {
  theme.value = value;
  document.documentElement.classList.toggle("dark", value === "dark");
}

function getSystemTheme(): ThemeMode {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

let isInitialized = false;

export function useTheme() {
  const initializeTheme = (): void => {
    if (isInitialized) {
      return;
    }

    const savedTheme = getThemePreference();
    applyTheme(savedTheme ?? getSystemTheme());
    isInitialized = true;
  };

  const toggleTheme = (): void => {
    const nextTheme: ThemeMode = theme.value === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    setThemePreference(nextTheme);
  };

  return {
    initializeTheme,
    theme,
    toggleTheme,
  };
}

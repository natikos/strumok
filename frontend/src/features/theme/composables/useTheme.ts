import { ref } from "vue";

import type { ThemeMode } from "@/features/preferences/preferences.storage";

const theme = ref<ThemeMode>("light");

function applyTheme(value: ThemeMode): void {
  theme.value = value;
  document.documentElement.classList.toggle("dark", value === "dark");
  document.documentElement.style.colorScheme = value;
}

function getSystemTheme(): ThemeMode {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useTheme() {
  const initializeTheme = (): void => {
    applyTheme(getSystemTheme());
  };

  const setTheme = (value: ThemeMode): void => {
    applyTheme(value);
  };

  const toggleTheme = (): ThemeMode => {
    const nextTheme: ThemeMode = theme.value === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    return nextTheme;
  };

  return {
    initializeTheme,
    setTheme,
    theme,
    toggleTheme,
  };
}

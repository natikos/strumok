import { computed, ref } from "vue";

import {
  getStoredTheme,
  storeTheme,
  type ThemeMode,
} from "@/features/preferences/preferences.storage";

const theme = ref<ThemeMode>("light");
const isDarkTheme = computed(() => theme.value === "dark");

function applyTheme(value: ThemeMode): void {
  theme.value = value;
  document.documentElement.classList.toggle("dark", value === "dark");
  document.documentElement.style.colorScheme = value;
  storeTheme(value);
}

export function useTheme() {
  const initializeTheme = (): void => {
    applyTheme(getStoredTheme());
  };

  const setTheme = (value: ThemeMode): void => {
    applyTheme(value);
  };

  const toggleTheme = (): ThemeMode => {
    const nextTheme: ThemeMode = isDarkTheme.value ? "light" : "dark";
    setTheme(nextTheme);
    return nextTheme;
  };

  return {
    initializeTheme,
    isDarkTheme,
    setTheme,
    theme,
    toggleTheme,
  };
}

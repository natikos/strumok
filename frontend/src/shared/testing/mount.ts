import { mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";
import { createI18n } from "vue-i18n";

import AppPreset from "@/preset";
import en from "@features/i18n/locales/en.json";
import ua from "@features/i18n/locales/ua.json";

type Locale = "en" | "ua";

const PRIMEVUE_OPTIONS = {
  theme: { options: { darkModeSelector: ".dark", prefix: "s" }, preset: AppPreset },
};

/**
 * Build a fresh i18n instance per mount.
 *
 * The app-level singleton in `@features/i18n` reads the stored language at import
 * time, so sharing it across tests leaks locale state between them.
 */
export function createTestI18n(locale: Locale = "en") {
  return createI18n({
    fallbackLocale: "en",
    legacy: false,
    locale,
    messages: { en, ua },
  });
}

/**
 * The plugins the real app installs, for spreading into a `mount` call:
 *
 * ```ts
 * mount(MyComponent, { props: { ... }, global: { plugins: appPlugins() } });
 * ```
 *
 * Prefer this over `mountWithPlugins` when a spec needs full prop type inference
 * or custom `global` options — it keeps `mount`'s own typing intact.
 */
export function appPlugins(locale: Locale = "en") {
  return [createTestI18n(locale), [PrimeVue, PRIMEVUE_OPTIONS] as [typeof PrimeVue, object]];
}

/**
 * Mount a component with the plugins the real app installs.
 *
 * `vitest.config.ts` deliberately omits the PrimeVue auto-import resolver, so
 * PrimeVue components used in a template are not registered globally the way they
 * are in `vite.config.ts`. Register the ones a component needs via
 * `global.components`, or stub them via `global.stubs`.
 */
export function mountWithPlugins(
  component: Parameters<typeof mount>[0],
  options: (Parameters<typeof mount>[1] & { locale?: Locale }) | undefined = {}
) {
  const { locale = "en", global: globalOptions, ...rest } = options ?? {};

  return mount(component, {
    ...rest,
    global: {
      ...globalOptions,
      plugins: [...appPlugins(locale), ...(globalOptions?.plugins ?? [])],
    },
  });
}

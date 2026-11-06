import { mount } from "@vue/test-utils";
import PrimeVue from "primevue/config";
import { defineComponent, h, type Plugin } from "vue";
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

// Tests don't install vue-router, which is what registers `RouterLink` in the app.
// A stub keeps templates using it from warning, and renders an `<a href>` from `to`
// so specs can assert the link target.
const RouterLinkStub = defineComponent({
  name: "RouterLink",
  props: { to: { default: "", type: [String, Object] } },
  setup(props, { slots }) {
    return () => h("a", { href: typeof props.to === "string" ? props.to : undefined }, slots["default"]?.());
  },
});

const routerLinkStubPlugin: Plugin = {
  install(app) {
    app.component("RouterLink", RouterLinkStub);
  },
};

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
  return [
    createTestI18n(locale),
    [PrimeVue, PRIMEVUE_OPTIONS] as [typeof PrimeVue, object],
    routerLinkStubPlugin,
  ];
}

/**
 * Mount a component with the plugins the real app installs.
 *
 * `vitest.config.ts` auto-imports components like `vite.config.ts` does, so
 * PrimeVue and our own components resolve without registration; stub heavy ones
 * via `global.stubs`.
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

import { PrimeVueResolver } from "@primevue/auto-import-resolver";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import Components from "unplugin-vue-components/vite";
import { defineConfig } from "vitest/config";

// Separate from vite.config.ts to avoid pulling in the PWA plugin, which isn't
// needed for unit tests. Components are auto-imported exactly as in the app, so a
// spec mounting a component sees the same children (PrimeVue and our own) the
// app does instead of "Failed to resolve component" warnings.
export default defineConfig({
  plugins: [
    vue(),
    Components({
      dirs: ["src"],
      dts: false,
      resolvers: [PrimeVueResolver()],
    }),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "@features": fileURLToPath(new URL("./src/features", import.meta.url)),
      "@pages": fileURLToPath(new URL("./src/pages", import.meta.url)),
      "@shared": fileURLToPath(new URL("./src/shared", import.meta.url)),
      "@utils": fileURLToPath(new URL("./src/shared/utils", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    isolate: true,
    globals: false,
    include: ["src/**/*.test.ts"],
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,vue}"],
      exclude: [
        "src/**/*.test.ts",
        "src/shared/api/generated/**",
        "src/shared/testing/**",
        "src/preset.ts",
        "src/main.ts",
      ],
    },
  },
});

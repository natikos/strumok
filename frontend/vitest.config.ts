import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

// Separate from vite.config.ts to avoid pulling in the PrimeVue auto-import
// resolver and PWA plugin, which aren't needed (and add noise) for unit tests.
export default defineConfig({
  plugins: [vue()],
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

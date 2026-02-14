import eslint from "@eslint/js";
import { defineConfigWithVueTs, vueTsConfigs } from "@vue/eslint-config-typescript";
import eslintConfigPrettier from "eslint-config-prettier/flat";
import perfectionist from "eslint-plugin-perfectionist";
import eslintPluginVue from "eslint-plugin-vue";
import globals from "globals";

export default defineConfigWithVueTs(
  { ignores: ["**/*.d.ts", "**/coverage", "**/dist"] },
  eslint.configs.recommended,
  ...eslintPluginVue.configs["flat/strongly-recommended"],
  vueTsConfigs.recommendedTypeChecked,
  {
    files: ["**/*.{ts,vue}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      perfectionist,
    },
    rules: {
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",
      "vue/max-attributes-per-line": [
        "error",
        {
          multiline: {
            max: 1,
          },
          singleline: {
            max: 2,
          },
        },
      ],
      "perfectionist/sort-imports": [
        "error",
        {
          customGroups: [
            {
              elementNamePattern: "^(?!\\.)",
              groupName: "external-style",
              selector: "style",
            },
            {
              elementNamePattern: "^\\.",
              groupName: "relative-style",
              selector: "style",
            },
          ],
          groups: [
            [
              "type-import",
              "external-style",
              "side-effect-builtin",
              "side-effect-external",
              "value-builtin",
              "value-external",
              "type-internal",
              "value-internal",
              "side-effect-internal",
              "side-effect-tsconfig-path",
              "type-parent",
              "type-sibling",
              "type-index",
              "ts-equals-import",
              "unknown",
            ],
            [
              "value-parent",
              "value-sibling",
              "value-index",
              "side-effect-parent",
              "side-effect-sibling",
              "side-effect-index",
              "relative-style",
            ],
          ],
          newlinesBetween: 1,
          order: "asc",
          sortSideEffects: true,
          type: "natural",
        },
      ],
      "perfectionist/sort-named-imports": [
        "error",
        {
          order: "asc",
          type: "natural",
        },
      ],
      "perfectionist/sort-objects": [
        "error",
        {
          order: "asc",
          type: "natural",
        },
      ],
    },
  },
  eslintConfigPrettier
);

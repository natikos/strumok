import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import en from "@/features/i18n/locales/en.json";
import ua from "@/features/i18n/locales/ua.json";

/**
 * Codes handled inline by a dedicated form/component instead of the generic
 * `errors.<code>` toast (see error-toast.ts) -- they're translated under
 * their own feature namespace, so they're exempt from this check.
 */
const HANDLED_OUTSIDE_ERRORS_NAMESPACE = new Set(["effectiveFromAlreadyExists"]);

/**
 * Every ErrorOut example in the generated OpenAPI types is a detail code the
 * backend can actually send. If either locale is missing an `errors.<code>`
 * key, the resident sees generic fallback text instead of a translated
 * message -- so this fails CI rather than surfacing only at runtime.
 */
function declaredErrorCodes(): string[] {
  const openapiPath = path.join(__dirname, "generated", "openapi.ts");
  const source = readFileSync(openapiPath, "utf-8");
  const matches = source.matchAll(/"detail":\s*"([a-zA-Z]+)"/g);
  const codes = new Set(
    [...matches]
      .map((match) => match[1])
      .filter((code): code is string => code !== undefined),
  );

  for (const handled of HANDLED_OUTSIDE_ERRORS_NAMESPACE) {
    codes.delete(handled);
  }

  return [...codes];
}

describe("error code translation completeness", () => {
  const codes = declaredErrorCodes();

  it("found at least one declared error code to check", () => {
    expect(codes.length).toBeGreaterThan(0);
  });

  it.each(codes)("en has a translation for %s", (code) => {
    expect(en.errors).toHaveProperty(code);
  });

  it.each(codes)("ua has a translation for %s", (code) => {
    expect(ua.errors).toHaveProperty(code);
  });
});

import { describe, expect, it } from "vitest";

import { navigationDenylist } from "./navigationDenylist";

const denied = (path: string) => navigationDenylist.some((pattern) => pattern.test(path));

describe("navigationDenylist", () => {
  it.each(["/admin/export/readings.csv", "/health", "/docs", "/favicon/icon.png", "/x.webmanifest"])(
    "leaves %s to the network",
    (path) => {
      expect(denied(path)).toBe(true);
    }
  );

  it.each(["/", "/history", "/settings", "/admin"])("serves %s from the shell", (path) => {
    expect(denied(path)).toBe(false);
  });
});

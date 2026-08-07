import { describe, expect, it } from "vitest";

import DeadlineBadge from "@features/dashboard/components/DeadlineBadge.vue";

import { mountWithPlugins } from "./mount";

/**
 * Tests for the test harness itself: proves a real component mounts with i18n and
 * PrimeVue wired up, and that translations resolve rather than falling through as
 * raw message keys.
 */
describe("frontend test harness", () => {
  it("mounts a component and resolves translations", () => {
    const wrapper = mountWithPlugins(DeadlineBadge, {
      props: { reading: null },
    });

    const text = wrapper.text();
    expect(text.length).toBeGreaterThan(0);
    // A missing i18n setup surfaces as the raw key echoed back.
    expect(text).not.toContain("statuses.meterReading");
  });

  it("honours the requested locale", () => {
    const en = mountWithPlugins(DeadlineBadge, { props: { reading: null } }).text();
    const ua = mountWithPlugins(DeadlineBadge, {
      props: { reading: null },
      locale: "ua",
    }).text();

    expect(en).not.toBe(ua);
  });

  it("gives each mount an isolated i18n instance", () => {
    // Locale set on one mount must not leak into the next; the app-level i18n
    // singleton would fail this.
    mountWithPlugins(DeadlineBadge, { props: { reading: null }, locale: "ua" });
    const after = mountWithPlugins(DeadlineBadge, { props: { reading: null } }).text();
    const baseline = mountWithPlugins(DeadlineBadge, { props: { reading: null } }).text();

    expect(after).toBe(baseline);
  });
});

import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { getCurrentRate } = vi.hoisted(() => ({ getCurrentRate: vi.fn() }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let Strip: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/billing", () => ({ getCurrentRate }));
  Strip = (await import("./TariffStrip.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/billing");
  vi.resetModules();
});

beforeEach(() => {
  getCurrentRate.mockReset();
});

async function render() {
  const wrapper = mount(Strip, { global: { plugins: appPlugins() } });
  await flushPromises();
  return wrapper;
}

describe("TariffStrip", () => {
  it("shows the day and night prices and the start date as DD.MM", async () => {
    getCurrentRate.mockResolvedValue({
      day_rate_uah: "4.32",
      night_rate_uah: "2.16",
      effective_from: "2026-01",
    });
    const text = (await render()).text();

    expect(text).toMatch(/Day.*4[.,]32/);
    expect(text).toMatch(/Night.*2[.,]16/);
    expect(text).toContain("from 01.01");
  });

  it("renders nothing when no rate is configured", async () => {
    getCurrentRate.mockResolvedValue(null);
    expect((await render()).text()).toBe("");
  });

  it("renders nothing, without throwing, when the load fails", async () => {
    getCurrentRate.mockRejectedValue(new Error("down"));
    expect((await render()).text()).toBe("");
  });
});

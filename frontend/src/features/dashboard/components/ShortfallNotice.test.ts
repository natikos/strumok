import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { getShortfall } = vi.hoisted(() => ({ getShortfall: vi.fn() }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let Notice: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/billing", () => ({ getShortfall }));
  Notice = (await import("./ShortfallNotice.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/billing");
  vi.resetModules();
});

beforeEach(() => {
  getShortfall.mockReset();
});

async function render() {
  const wrapper = mount(Notice, { global: { plugins: appPlugins() } });
  await flushPromises();
  return wrapper;
}

describe("ShortfallNotice", () => {
  it("shows the due date and amount when active", async () => {
    getShortfall.mockResolvedValue({ active: true, due_date: "2026-10-20", owed_uah: "450.00" });
    const text = (await render()).text();
    expect(text).toContain("20.10");
    expect(text).toContain("450");
  });

  it("renders nothing when inactive", async () => {
    getShortfall.mockResolvedValue({ active: false, due_date: null, owed_uah: "0.00" });
    expect((await render()).find(".shortfall").exists()).toBe(false);
  });

  it("renders nothing when it fails to load", async () => {
    getShortfall.mockRejectedValue(new Error("x"));
    expect((await render()).find(".shortfall").exists()).toBe(false);
  });
});

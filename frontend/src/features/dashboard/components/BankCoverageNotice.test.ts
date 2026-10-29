import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { getBankCoverage } = vi.hoisted(() => ({ getBankCoverage: vi.fn() }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let Notice: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/billing", () => ({ getBankCoverage }));
  Notice = (await import("./BankCoverageNotice.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/billing");
  vi.resetModules();
});

beforeEach(() => {
  getBankCoverage.mockReset();
});

async function render() {
  const wrapper = mount(Notice, { global: { plugins: appPlugins() } });
  await flushPromises();
  return wrapper;
}

describe("BankCoverageNotice", () => {
  it("shows the coverage date as DD.MM", async () => {
    getBankCoverage.mockResolvedValue({
      covered_through: "2026-05-17",
      awaiting_statement: false,
      last_imported_at: null,
    });
    expect((await render()).text()).toContain("17.05");
  });

  it("shows the awaiting notice when never imported", async () => {
    getBankCoverage.mockResolvedValue({
      covered_through: null,
      awaiting_statement: true,
      last_imported_at: null,
    });
    const wrapper = await render();
    expect(wrapper.classes()).toContain("bank-coverage--awaiting");
  });

  it("shows the last import time for the head", async () => {
    getBankCoverage.mockResolvedValue({
      covered_through: "2026-05-17",
      awaiting_statement: false,
      last_imported_at: "2026-05-18T08:00:00Z",
    });
    expect((await render()).find(".bank-coverage__import").exists()).toBe(true);
  });

  it("renders nothing when coverage fails to load", async () => {
    getBankCoverage.mockRejectedValue(new Error("x"));
    expect((await render()).find(".bank-coverage").exists()).toBe(false);
  });
});

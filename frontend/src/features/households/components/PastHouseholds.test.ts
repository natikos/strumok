import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { listMyStatements } = vi.hoisted(() => ({ listMyStatements: vi.fn() }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let PastHouseholds: Component;
let PastHouseholdNotice: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/billing", () => ({ listMyStatements }));
  PastHouseholds = (await import("./PastHouseholds.vue")).default;
  PastHouseholdNotice = (await import("./PastHouseholdNotice.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/billing");
  vi.resetModules();
});

const tenure = (overrides = {}) => ({
  household_id: 7,
  household_name: "Plot 7",
  is_current_owner: false,
  has_previous_owner: false,
  owned_since: "2023-01-01T00:00:00Z",
  owned_until: "2024-02-10T10:00:00Z",
  balance: { balance_uah: "212.00" },
  statements: [{ period: "2024-01", total_uah: "300.00" }],
  ...overrides,
});

const mountIt = (component: Component) => mount(component, { global: { plugins: appPlugins() } });

describe("past households", () => {
  beforeEach(() => {
    listMyStatements.mockReset();
  });

  it("tells the old owner they no longer own the plot, with the date", async () => {
    listMyStatements.mockResolvedValue([tenure()]);
    const wrapper = mountIt(PastHouseholdNotice);
    await flushPromises();

    expect(wrapper.text()).toContain("You no longer own Plot 7 as of");
    expect(wrapper.text()).toContain("2024");
  });

  it("lists a gave-up plot read-only with its balance and bills", async () => {
    listMyStatements.mockResolvedValue([tenure()]);
    const wrapper = mountIt(PastHouseholds);
    await flushPromises();

    expect(wrapper.text()).toContain("Past households");
    expect(wrapper.text()).toContain("Plot 7");
    expect(wrapper.text()).toContain("You owe");
    expect(wrapper.text()).toContain("212");
    expect(wrapper.text()).toContain("300");
    expect(wrapper.find("button").exists()).toBe(false);
  });

  it("shows nothing for plots the user still owns", async () => {
    listMyStatements.mockResolvedValue([tenure({ is_current_owner: true })]);
    const notice = mountIt(PastHouseholdNotice);
    const list = mountIt(PastHouseholds);
    await flushPromises();

    expect(notice.text()).toBe("");
    expect(list.text()).toBe("");
  });

  it("shows nothing when the request fails", async () => {
    listMyStatements.mockRejectedValue(new Error("boom"));
    const wrapper = mountIt(PastHouseholds);
    await flushPromises();

    expect(wrapper.text()).toBe("");
  });
});

import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { getBalance } = vi.hoisted(() => ({ getBalance: vi.fn() }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let BalanceStrip: Component;
let setHouseholds: (households: { id: number; name: string }[]) => unknown;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/billing", () => ({ getBalance }));
  BalanceStrip = (await import("./BalanceStrip.vue")).default;
  // Same module instance as the component imports after the reset.
  const household = await import("@/features/households/useCurrentHousehold");
  setHouseholds = household.useCurrentHousehold().setHouseholds;
});

afterAll(() => {
  vi.doUnmock("@shared/api/billing");
  vi.resetModules();
});

const balance = (overrides = {}) => ({
  balance_uah: "0.00",
  household_id: 1,
  periods: [],
  total_due_uah: "0.00",
  total_paid_uah: "0.00",
  unpaid_months: 0,
  ...overrides,
});

function mountStrip() {
  return mount(BalanceStrip, {
    global: { plugins: appPlugins(), stubs: { ErrorState: true, Skeleton: true } },
  });
}

describe("BalanceStrip", () => {
  beforeEach(() => {
    getBalance.mockReset();
    setHouseholds([{ id: 1, name: "Plot 1" }]);
  });

  it("says what is owed and how many months are unpaid", async () => {
    getBalance.mockResolvedValue(balance({ balance_uah: "250.00", unpaid_months: 2 }));
    const wrapper = mountStrip();
    await flushPromises();

    expect(wrapper.text()).toContain("You owe");
    expect(wrapper.text()).toContain("250");
    expect(wrapper.text()).toContain("2 unpaid month(s)");
  });

  it("shows a positive all-paid-up state, not an absent element", async () => {
    getBalance.mockResolvedValue(balance());
    const wrapper = mountStrip();
    await flushPromises();

    expect(wrapper.text()).toContain("You're all paid up");
  });

  it("shows a credit when the household has overpaid", async () => {
    getBalance.mockResolvedValue(balance({ balance_uah: "-40.00" }));
    const wrapper = mountStrip();
    await flushPromises();

    expect(wrapper.text()).toContain("Credit:");
    expect(wrapper.text()).toContain("40");
  });

  it("never claims everything is paid when the balance failed to load", async () => {
    getBalance.mockRejectedValue(new Error("down"));
    const wrapper = mountStrip();
    await flushPromises();

    expect(wrapper.text()).not.toContain("all paid up");
    expect(wrapper.findComponent({ name: "ErrorState" }).exists()).toBe(true);
  });

  it("names the household only when the user has more than one", async () => {
    getBalance.mockResolvedValue(balance({ balance_uah: "10.00", unpaid_months: 1 }));
    setHouseholds([
      { id: 1, name: "Plot 1" },
      { id: 2, name: "Plot 2" },
    ]);
    const wrapper = mountStrip();
    await flushPromises();

    expect(wrapper.find(".balance-strip__household").text()).toBe("Plot 1");
  });
});

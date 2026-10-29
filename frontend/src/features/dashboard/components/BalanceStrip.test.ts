import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { getBalance, getPaymentDetails, listMyStatements } = vi.hoisted(() => ({
  getBalance: vi.fn(),
  getPaymentDetails: vi.fn(),
  listMyStatements: vi.fn(),
}));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let BalanceStrip: Component;
let PaySheet: Component;
let setHouseholds: (households: { id: number; name: string }[]) => unknown;
let setPastOnly: (value: boolean) => void;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/billing", () => ({ getBalance, getPaymentDetails, listMyStatements }));
  BalanceStrip = (await import("./BalanceStrip.vue")).default;
  PaySheet = (await import("./PaySheet.vue")).default;
  // Same module instance as the component imports after the reset.
  const household = await import("@/features/households/useCurrentHousehold");
  setHouseholds = household.useCurrentHousehold().setHouseholds;
  setPastOnly = household.useCurrentHousehold().setPastOnly;
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
    global: {
      plugins: appPlugins(),
      components: { Button, PaySheet },
      stubs: { ErrorState: true, Skeleton: true, Dialog: { template: "<div><slot /></div>" } },
    },
  });
}

describe("BalanceStrip", () => {
  beforeEach(() => {
    getBalance.mockReset();
    getPaymentDetails.mockReset().mockResolvedValue(null);
    listMyStatements.mockReset().mockResolvedValue([]);
    setHouseholds([{ id: 1, name: "Plot 1" }]);
    setPastOnly(false);
  });

  describe("past-only (no plot left)", () => {
    const details = { iban: "UA213223130000026007233566001", recipient_name: "Strumok Co-op" };
    const past = (id: number, amount: string) => ({
      household_id: id,
      is_current_owner: false,
      balance: balance({ household_id: id, balance_uah: amount }),
    });

    beforeEach(() => {
      setHouseholds([]);
      setPastOnly(true);
    });

    it("does not request a current-plot balance and shows what is owed on gave-up plots", async () => {
      listMyStatements.mockResolvedValue([past(9, "212.40")]);
      const wrapper = mountStrip();
      await flushPromises();

      expect(getBalance).not.toHaveBeenCalled();
      expect(wrapper.text()).toContain("You owe");
      expect(wrapper.text()).toContain("212");
    });

    it("pays only for the gave-up plots that owe, referencing exactly those plots", async () => {
      getPaymentDetails.mockResolvedValue(details);
      listMyStatements.mockResolvedValue([past(9, "100.10"), past(11, "-40.00"), past(12, "50.20")]);
      const wrapper = mountStrip();
      await flushPromises();

      expect(wrapper.find(".balance-strip__pay").exists()).toBe(true);
      const props = wrapper.findComponent({ name: "PaySheet" }).props();
      expect(props.comment).toContain("STR-9");
      expect(props.comment).toContain("STR-12");
      expect(props.comment).not.toContain("STR-11");
      expect(props.amount).toBe("150.30");
    });

    it("shows the net owed but pays only the owing plot when another is in credit", async () => {
      getPaymentDetails.mockResolvedValue(details);
      listMyStatements.mockResolvedValue([past(21, "500.00"), past(22, "-200.00")]);
      const wrapper = mountStrip();
      await flushPromises();

      expect(wrapper.text()).toContain("You owe");
      expect(wrapper.text()).toContain("300");
      const props = wrapper.findComponent({ name: "PaySheet" }).props();
      expect(props.amount).toBe("500.00");
      expect(props.comment).toContain("STR-21");
      expect(props.comment).not.toContain("STR-22");
    });

    it("offers no Pay when gave-up plots are all paid or in credit", async () => {
      getPaymentDetails.mockResolvedValue(details);
      listMyStatements.mockResolvedValue([past(9, "-40.00")]);
      const wrapper = mountStrip();
      await flushPromises();

      expect(wrapper.find(".balance-strip__pay").exists()).toBe(false);
    });
  });

  it("says what is owed and how many months are unpaid", async () => {
    getBalance.mockResolvedValue(balance({ balance_uah: "250.00", unpaid_months: 2 }));
    const wrapper = mountStrip();
    await flushPromises();

    expect(wrapper.text()).toContain("You owe");
    expect(wrapper.text()).toContain("250");
    expect(wrapper.text()).toContain("2 unpaid month(s)");
  });

  it("still counts what is owed on a plot the user gave up", async () => {
    getBalance.mockResolvedValue(balance({ balance_uah: "100.00" }));
    listMyStatements.mockResolvedValue([
      { household_id: 9, is_current_owner: false, balance: balance({ balance_uah: "212.00" }) },
    ]);
    const wrapper = mountStrip();
    await flushPromises();

    expect(wrapper.text()).toContain("You owe");
    expect(wrapper.text()).toContain("312");
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

  describe("pay action", () => {
    const details = { iban: "UA213223130000026007233566001", recipient_name: "Strumok Co-op" };

    it("offers Pay with this plot's balance when money is owed and details exist", async () => {
      getBalance.mockResolvedValue(balance({ balance_uah: "250.50" }));
      getPaymentDetails.mockResolvedValue(details);
      const wrapper = mountStrip();
      await flushPromises();

      expect(wrapper.find(".balance-strip__pay").exists()).toBe(true);

      expect(wrapper.findComponent({ name: "PaySheet" }).props()).toMatchObject({
        amount: "250.50",
        iban: details.iban,
        recipient: "Strumok Co-op",
        comment: "Electricity STR-1",
      });
    });

    it("hides Pay when nothing is owed", async () => {
      getBalance.mockResolvedValue(balance({ balance_uah: "-10.00" }));
      getPaymentDetails.mockResolvedValue(details);
      const wrapper = mountStrip();
      await flushPromises();

      expect(wrapper.find(".balance-strip__pay").exists()).toBe(false);
    });

    it("hides Pay when the head has not set payment details", async () => {
      getBalance.mockResolvedValue(balance({ balance_uah: "250.00" }));
      const wrapper = mountStrip();
      await flushPromises();

      expect(wrapper.find(".balance-strip__pay").exists()).toBe(false);
    });

    it("keeps the balance visible when payment details fail to load", async () => {
      getBalance.mockResolvedValue(balance({ balance_uah: "250.00" }));
      getPaymentDetails.mockRejectedValue(new Error("boom"));
      const wrapper = mountStrip();
      await flushPromises();

      expect(wrapper.text()).toContain("You owe");
      expect(wrapper.find(".balance-strip__pay").exists()).toBe(false);
    });
  });
});

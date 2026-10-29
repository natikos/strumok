import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const api = vi.hoisted(() => ({
  correctOpeningBalance: vi.fn(),
  getOpeningBalance: vi.fn(),
  listAdminBalances: vi.fn(),
  listHouseholdPayments: vi.fn(),
  recordHouseholdPayment: vi.fn(),
  setOpeningBalance: vi.fn(),
  voidHouseholdPayment: vi.fn(),
}));
const { confirmRequire } = vi.hoisted(() => ({ confirmRequire: vi.fn() }));

vi.mock("primevue/useconfirm", () => ({ useConfirm: () => ({ require: confirmRequire }) }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let BalancesPanel: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => api);
  BalancesPanel = (await import("./BalancesPanel.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

const balances = {
  households: [
    {
      balance_uah: "300.00",
      household_id: 1,
      household_name: "Plot 1",
      owner_name: "Ada Owner",
      unpaid_months: 2,
    },
    {
      balance_uah: "-20.00",
      household_id: 2,
      household_name: "Plot 2",
      owner_name: null,
      unpaid_months: 0,
    },
  ],
  total_outstanding_uah: "300.00",
};

const payment = {
  amount_uah: "100.00",
  created_at: "2026-10-01T10:00:00Z",
  household_id: 1,
  id: 9,
  method: "cash",
  note: null,
  paid_on: "2026-10-01",
  void_reason: null,
  voided_at: null,
};

function mountPanel() {
  return mount(BalancesPanel, {
    global: {
      components: { Button, InputNumber, InputText, Select },
      plugins: appPlugins(),
      stubs: { ErrorState: true, Skeleton: true },
    },
  });
}

describe("BalancesPanel", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        addEventListener: vi.fn(),
        matches: false,
        removeEventListener: vi.fn(),
      })
    );
    confirmRequire.mockReset();
    Object.values(api).forEach((fn) => fn.mockReset());
    api.listAdminBalances.mockResolvedValue(balances);
    api.listHouseholdPayments.mockResolvedValue([payment]);
    api.getOpeningBalance.mockResolvedValue(null);
  });

  it("shows the total outstanding and who owes what, with credits labelled", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain("Total outstanding");
    expect(wrapper.text()).toContain("Owes");
    expect(wrapper.text()).toContain("Credit");
  });

  it("gives every record-payment action an accessible name with the household", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    const labels = wrapper.findAll("button").map((b) => b.attributes("aria-label"));
    expect(labels).toContain("Record payment for Plot 1");
    expect(labels).toContain("Record payment for Plot 2");
  });

  it("pre-fills the amount with the balance and records without a confirm", async () => {
    api.recordHouseholdPayment.mockResolvedValue(payment);
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find("button[aria-label='Record payment for Plot 1']").trigger("click");
    await flushPromises();
    await wrapper.find(".balances__form").trigger("submit");
    await flushPromises();

    expect(confirmRequire).not.toHaveBeenCalled();
    expect(api.recordHouseholdPayment).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ amount_uah: "300", method: "cash" })
    );
  });

  it("requires a reason before a void can be confirmed", async () => {
    const wrapper = mountPanel();
    await flushPromises();
    await wrapper.find("button[aria-label='Record payment for Plot 1']").trigger("click");
    await flushPromises();

    const voidButton = wrapper.find(".balances__payment button");
    expect(voidButton.attributes("disabled")).toBeDefined();

    await wrapper.find(".balances__payment input").setValue("bounced");
    expect(wrapper.find(".balances__payment button").attributes("disabled")).toBeUndefined();

    await wrapper.find(".balances__payment button").trigger("click");
    expect(confirmRequire).toHaveBeenCalledTimes(1);
  });

  it("strikes through a voided payment and keeps its reason visible", async () => {
    api.listHouseholdPayments.mockResolvedValue([
      { ...payment, void_reason: "wrong plot", voided_at: "2026-10-02T10:00:00Z" },
    ]);
    const wrapper = mountPanel();
    await flushPromises();
    await wrapper.find("button[aria-label='Record payment for Plot 1']").trigger("click");
    await flushPromises();

    expect(wrapper.find(".balances__payment--voided").exists()).toBe(true);
    expect(wrapper.text()).toContain("Voided: wrong plot");
  });
});

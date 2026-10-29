import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const api = vi.hoisted(() => ({
  confirmBankTransaction: vi.fn(),
  dismissBankTransaction: vi.fn(),
  linkBankTransaction: vi.fn(),
  listAdminHouseholds: vi.fn(),
  listBankQueue: vi.fn(),
}));
const { confirmRequire } = vi.hoisted(() => ({ confirmRequire: vi.fn() }));

vi.mock("primevue/useconfirm", () => ({ useConfirm: () => ({ require: confirmRequire }) }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let BankQueuePanel: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => api);
  BankQueuePanel = (await import("./BankQueuePanel.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

const credit = {
  id: 5,
  operation_date: "2026-10-10",
  amount_uah: "500.00",
  payer_name: "Payer",
  purpose: "plot 1",
  suggested_household_id: 1,
  suggestion_source: null,
  link_candidates: [{ payment_id: 9, household_id: 1, paid_on: "2026-10-08" }],
};

function mountPanel() {
  return mount(BankQueuePanel, {
    global: {
      components: { Button, InputNumber },
      plugins: appPlugins(),
      stubs: { ErrorState: true, Select: true },
    },
  });
}

function buttonByText(wrapper: ReturnType<typeof mountPanel>, text: string) {
  return wrapper.findAllComponents(Button).find((button) => button.text().includes(text));
}

describe("BankQueuePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listBankQueue.mockResolvedValue([credit]);
    api.listAdminHouseholds.mockResolvedValue([{ id: 1, name: "Plot 1" }]);
    api.confirmBankTransaction.mockResolvedValue([]);
  });

  it("shows the empty state", async () => {
    api.listBankQueue.mockResolvedValue([]);
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain("No credits to review");
  });

  it("asks for confirmation and creates nothing until accepted", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    await buttonByText(wrapper, "Confirm")?.trigger("click");

    expect(api.confirmBankTransaction).not.toHaveBeenCalled();
    expect(confirmRequire).toHaveBeenCalledOnce();

    confirmRequire.mock.calls[0]?.[0].accept();
    await flushPromises();

    expect(api.confirmBankTransaction).toHaveBeenCalledWith(5, [
      { household_id: 1, amount_uah: "500.00" },
    ]);
  });

  it("dismisses only after confirmation", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    await buttonByText(wrapper, "Not a resident payment")?.trigger("click");
    expect(api.dismissBankTransaction).not.toHaveBeenCalled();

    confirmRequire.mock.calls[0]?.[0].accept();
    await flushPromises();

    expect(api.dismissBankTransaction).toHaveBeenCalledWith(5);
  });

  it("links to a candidate manual transfer", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    await buttonByText(wrapper, "Link to Plot 1")?.trigger("click");
    expect(api.linkBankTransaction).not.toHaveBeenCalled();

    confirmRequire.mock.calls[0]?.[0].accept();
    await flushPromises();

    expect(api.linkBankTransaction).toHaveBeenCalledWith(5, 9);
  });
});

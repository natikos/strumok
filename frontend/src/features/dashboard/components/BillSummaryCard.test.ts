import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const api = vi.hoisted(() => ({ listAdjustments: vi.fn(), listStatements: vi.fn() }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let BillSummaryCard: Component;
let BillBreakdown: Component;
let setHouseholds: (households: { id: number; name: string }[]) => unknown;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/billing", () => api);
  BillSummaryCard = (await import("./BillSummaryCard.vue")).default;
  BillBreakdown = (await import("./BillBreakdown.vue")).default;
  setHouseholds = (
    await import("@/features/households/useCurrentHousehold")
  ).useCurrentHousehold().setHouseholds;
});

afterAll(() => {
  vi.doUnmock("@shared/api/billing");
  vi.resetModules();
});

const closedLine = (overrides = {}) => ({
  day_usage_kwh: "100.00",
  is_estimated: false,
  loss_share_uah: "12.34",
  night_usage_kwh: "40.00",
  penalty_credit_uah: "0.00",
  penalty_uah: "0.00",
  period: "2026-09",
  status: "closed",
  tariff_uah: "500.10",
  total_uah: "512.44",
  ...overrides,
});

function mountCard() {
  return mount(BillSummaryCard, {
    global: {
      components: { BillBreakdown, Button },
      plugins: appPlugins(),
      stubs: { ErrorState: true, Skeleton: true },
    },
  });
}

describe("BillSummaryCard", () => {
  beforeEach(() => {
    api.listStatements.mockReset();
    api.listAdjustments.mockReset().mockResolvedValue([]);
    setHouseholds([{ id: 1, name: "Plot 1" }]);
  });

  it("leads with the latest closed bill and a plain-language line, without jargon", async () => {
    api.listStatements.mockResolvedValue([closedLine()]);
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.find(".bill-summary__amount").text()).toContain("512");
    expect(wrapper.text()).toContain("shared costs");
    expect(wrapper.text()).not.toMatch(/reconciliation|pro-rata|loss/i);
  });

  it("expands a breakdown whose rows add up to the total shown", async () => {
    api.listStatements.mockResolvedValue([closedLine()]);
    api.listAdjustments.mockResolvedValue([
      { amount_uah: "-12.40", applies_to_period: "2026-09", id: 1, posted_in_period: "2026-10", reason: "bill corrected", reason_code: "billCorrection" },
    ]);
    const wrapper = mountCard();
    await flushPromises();

    await wrapper.find(".bill-summary__toggle").trigger("click");

    const amounts = wrapper
      .findAll(".bill-breakdown__row dd")
      .map((dd) => dd.text());
    expect(wrapper.text()).toContain("bill corrected");
    expect(amounts.at(-1)).toContain("500.04"); // 500.10 + 12.34 - 12.40
    expect(wrapper.find(".bill-summary__amount").text()).toContain("500.04");
  });

  it("marks an estimated period with an Estimated pill and its own copy", async () => {
    api.listStatements.mockResolvedValue([
      closedLine({ is_estimated: true, loss_share_uah: "0.00", penalty_uah: "30.00", total_uah: "530.10" }),
    ]);
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.find(".bill-summary__pill").text()).toContain("Estimated");
    expect(wrapper.text()).toContain("30% late fee");
  });

  it("renders nothing - not 0.00 - before any period has closed, but shows the provisional line", async () => {
    api.listStatements.mockResolvedValue([closedLine({ status: "provisional" })]);
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.find(".bill-summary").exists()).toBe(false);
  });

  it("shows the error block on a failed load, never the empty state", async () => {
    api.listStatements.mockRejectedValue(new Error("down"));
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.findComponent({ name: "ErrorState" }).exists()).toBe(true);
    expect(wrapper.find(".bill-summary").exists()).toBe(false);
  });
});

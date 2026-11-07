import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const api = vi.hoisted(() => ({ listAdjustments: vi.fn(), listStatements: vi.fn() }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let BillSummaryCard: Component;
let setHouseholds: (households: { id: number; name: string }[]) => unknown;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/billing", () => api);
  BillSummaryCard = (await import("./BillSummaryCard.vue")).default;
  setHouseholds = (await import("@/features/households/useCurrentHousehold")).useCurrentHousehold()
    .setHouseholds;
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
      {
        amount_uah: "-12.40",
        applies_to_period: "2026-09",
        id: 1,
        posted_in_period: "2026-10",
        reason: "bill corrected",
        reason_code: "billCorrection",
      },
    ]);
    const wrapper = mountCard();
    await flushPromises();

    await wrapper.find(".bill-summary__toggle").trigger("click");

    const amounts = wrapper.findAll(".bill-breakdown__row dd").map((dd) => dd.text());
    expect(wrapper.text()).toContain("bill corrected");
    expect(amounts.at(-1)).toContain("500.04"); // 500.10 + 12.34 - 12.40
    expect(wrapper.find(".bill-summary__amount").text()).toContain("500.04");
  });

  it("marks an estimated period with an Estimated pill and its own copy", async () => {
    api.listStatements.mockResolvedValue([
      closedLine({
        is_estimated: true,
        loss_share_uah: "0.00",
        penalty_uah: "30.00",
        total_uah: "530.10",
      }),
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

  describe("'What is included' toggle", () => {
    const toggle = (wrapper: ReturnType<typeof mountCard>) =>
      wrapper.findAll("button").filter((b) => b.text().includes("What is included"));

    it("is absent for a tariff-only bill", async () => {
      api.listStatements.mockResolvedValue([closedLine({ loss_share_uah: "0.00" })]);
      const wrapper = mountCard();
      await flushPromises();

      expect(wrapper.find(".bill-summary").exists()).toBe(true);
      expect(toggle(wrapper)).toHaveLength(0);
    });

    it.each([
      ["a shared-loss row", {}],
      ["a late-fee row", { loss_share_uah: "0.00", penalty_uah: "30.00" }],
      ["a late-fee credit row", { loss_share_uah: "0.00", penalty_credit_uah: "4.50" }],
    ])("is present and opens the breakdown for %s", async (_name, overrides) => {
      api.listStatements.mockResolvedValue([closedLine(overrides)]);
      const wrapper = mountCard();
      await flushPromises();

      expect(wrapper.find(".bill-breakdown__row").exists()).toBe(false);
      const buttons = toggle(wrapper);
      expect(buttons).toHaveLength(1);
      await buttons[0]!.trigger("click");
      expect(wrapper.find(".bill-breakdown__row").exists()).toBe(true);
    });

    it("is present for a tariff-only bill that has a correction", async () => {
      api.listStatements.mockResolvedValue([closedLine({ loss_share_uah: "0.00" })]);
      api.listAdjustments.mockResolvedValue([
        {
          amount_uah: "-1.00",
          applies_to_period: "2026-09",
          id: 1,
          posted_in_period: "2026-10",
          reason: "bill corrected",
          reason_code: "billCorrection",
        },
      ]);
      const wrapper = mountCard();
      await flushPromises();

      expect(toggle(wrapper)).toHaveLength(1);
    });
  });

  it("shows aria-busy skeletons while loading and none once loaded", async () => {
    let resolve!: (value: unknown) => void;
    api.listStatements.mockReturnValue(new Promise((r) => (resolve = r)));
    const wrapper = mountCard();
    await nextTick();

    expect(wrapper.find('[aria-busy="true"]').exists()).toBe(true);
    expect(wrapper.findAllComponents({ name: "Skeleton" }).length).toBeGreaterThan(0);

    resolve([closedLine()]);
    await flushPromises();

    expect(wrapper.find('[aria-busy="true"]').exists()).toBe(false);
    expect(wrapper.findAllComponents({ name: "Skeleton" })).toHaveLength(0);
  });
});

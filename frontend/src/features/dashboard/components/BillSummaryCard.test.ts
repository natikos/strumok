import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import { deferred, expectLoaded, expectLoading } from "@/shared/testing/loading";
import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const api = vi.hoisted(() => ({ getBalance: vi.fn(), listStatements: vi.fn() }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let BillSummaryCard: Component;
let setHouseholds: (households: { id: number; name: string }[]) => unknown;
let setPastOnly: (value: boolean) => void;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/billing", () => api);
  BillSummaryCard = (await import("./BillSummaryCard.vue")).default;
  const household = (await import("@/features/households/useCurrentHousehold")).useCurrentHousehold();
  setHouseholds = household.setHouseholds;
  setPastOnly = household.setPastOnly;
});

afterAll(() => {
  vi.doUnmock("@shared/api/billing");
  vi.resetModules();
});

const period = (name: string, due: string, paid = "0.00") => ({
  due_uah: due,
  paid_uah: paid,
  period: name,
  status: paid === "0.00" ? "unpaid" : "partial",
});

const balance = (periods: ReturnType<typeof period>[]) => ({
  balance_uah: "0",
  household_id: 1,
  periods,
  total_due_uah: "0",
  total_paid_uah: "0",
  unpaid_months: periods.length,
});

const provisionalLine = { period: "2026-10", status: "provisional", total_uah: "300.00" };

function mountCard() {
  return mount(BillSummaryCard, {
    global: {
      plugins: appPlugins(),
      stubs: {
        BalanceStrip: { template: '<div class="balance-strip-stub" />' },
        BankCoverageNotice: true,
        ErrorState: true,
        ShortfallNotice: true,
        Skeleton: true,
      },
    },
  });
}

describe("BillSummaryCard", () => {
  beforeEach(() => {
    api.listStatements.mockReset();
    api.getBalance.mockReset();
    setHouseholds([{ id: 1, name: "Plot 1" }]);
    setPastOnly(false);
  });

  it("leads with the balance and lists each month with what is left of it", async () => {
    api.listStatements.mockResolvedValue([provisionalLine]);
    api.getBalance.mockResolvedValue(
      balance([period("2026-08", "500.00"), period("2026-09", "800.00", "200.00")])
    );
    const wrapper = mountCard();
    await flushPromises();

    const rows = wrapper.findAll(".bill-summary__row");
    expect(rows).toHaveLength(3);
    expect(rows[0]!.text()).toContain("2026-10");
    expect(rows[1]!.text()).toContain("2026-09");
    expect(rows[1]!.text()).toContain("600");
    expect(rows[2]!.text()).toContain("2026-08");
    expect(wrapper.find(".balance-strip-stub").exists()).toBe(true);
  });

  it("skips fully paid months", async () => {
    api.listStatements.mockResolvedValue([provisionalLine]);
    api.getBalance.mockResolvedValue(balance([period("2026-09", "800.00", "800.00")]));
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.findAll(".bill-summary__row")).toHaveLength(1);
  });

  it("keeps the balance but lists no months when nothing is owed and no month is open", async () => {
    api.listStatements.mockResolvedValue([]);
    api.getBalance.mockResolvedValue(balance([]));
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.find(".balance-strip-stub").exists()).toBe(true);
    expect(wrapper.find(".bill-summary__rows").exists()).toBe(false);
  });

  it("has no month lines and fetches no statements for a former owner with no plot", async () => {
    setPastOnly(true);
    const wrapper = mountCard();
    await flushPromises();

    expect(api.listStatements).not.toHaveBeenCalled();
    expect(wrapper.find(".balance-strip-stub").exists()).toBe(true);
    expect(wrapper.find(".bill-summary__rows").exists()).toBe(false);
  });

  it("shows the error block on a failed load, never the empty state", async () => {
    api.listStatements.mockRejectedValue(new Error("down"));
    api.getBalance.mockResolvedValue(balance([]));
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.findComponent({ name: "ErrorState" }).exists()).toBe(true);
    expect(wrapper.find(".bill-summary__rows").exists()).toBe(false);
  });

  it("shows aria-busy skeletons while loading and none once loaded", async () => {
    const gate = deferred<unknown>();
    api.listStatements.mockReturnValue(gate.promise);
    api.getBalance.mockResolvedValue(balance([]));
    const wrapper = mountCard();
    await nextTick();

    expectLoading(wrapper);

    gate.resolve([provisionalLine]);
    await flushPromises();

    expectLoaded(wrapper);
  });
});

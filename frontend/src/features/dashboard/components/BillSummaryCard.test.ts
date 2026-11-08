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
      stubs: { ErrorState: true, Skeleton: true },
    },
  });
}

describe("BillSummaryCard", () => {
  beforeEach(() => {
    api.listStatements.mockReset();
    api.getBalance.mockReset();
    setHouseholds([{ id: 1, name: "Plot 1" }]);
  });

  it("leads with the total owed and lists each month with what is left of it", async () => {
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
    // 300 + 600 + 500
    expect(wrapper.find(".bill-summary__amount").text()).toContain("1,400");
  });

  it("skips fully paid months", async () => {
    api.listStatements.mockResolvedValue([provisionalLine]);
    api.getBalance.mockResolvedValue(balance([period("2026-09", "800.00", "800.00")]));
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.findAll(".bill-summary__row")).toHaveLength(1);
  });

  it("renders nothing when nothing is owed and no month is open", async () => {
    api.listStatements.mockResolvedValue([]);
    api.getBalance.mockResolvedValue(balance([]));
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.find(".bill-summary").exists()).toBe(false);
  });

  it("shows the error block on a failed load, never the empty state", async () => {
    api.listStatements.mockRejectedValue(new Error("down"));
    api.getBalance.mockResolvedValue(balance([]));
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.findComponent({ name: "ErrorState" }).exists()).toBe(true);
    expect(wrapper.find(".bill-summary").exists()).toBe(false);
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

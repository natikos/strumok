import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { closeAdminPeriod, confirmRequire, listAdminPeriods } = vi.hoisted(() => ({
  closeAdminPeriod: vi.fn(),
  confirmRequire: vi.fn(),
  listAdminPeriods: vi.fn(),
}));

vi.mock("primevue/useconfirm", () => ({ useConfirm: () => ({ require: confirmRequire }) }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let PeriodCloseCard: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => ({ closeAdminPeriod, listAdminPeriods }));
  PeriodCloseCard = (await import("./PeriodCloseCard.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

const open = {
  blockers: [] as string[],
  closed_at: null,
  closed_by_name: null,
  missing_count: 2,
  period: "2026-09",
  readings_count: 28,
  status: "open",
};

function mountCard() {
  return mount(PeriodCloseCard, {
    props: { period: "2026-09" },
    global: { components: { Button }, plugins: appPlugins() },
  });
}

describe("PeriodCloseCard", () => {
  beforeEach(() => {
    closeAdminPeriod.mockReset();
    confirmRequire.mockReset();
    listAdminPeriods.mockReset().mockResolvedValue([open]);
  });

  it("asks for confirmation with the exact counts before closing", async () => {
    const wrapper = mountCard();
    await flushPromises();

    await wrapper.find("button").trigger("click");

    expect(closeAdminPeriod).not.toHaveBeenCalled();
    const options = confirmRequire.mock.calls[0]![0] as { accept: () => void; message: string };
    expect(options.message).toContain("28 household(s) will be charged and 2 have no reading");

    closeAdminPeriod.mockResolvedValue({ ...open, closed_at: "2026-10-08T10:00:00Z", status: "closed" });
    options.accept();
    await flushPromises();

    expect(closeAdminPeriod).toHaveBeenCalledWith("2026-09");
    expect(wrapper.text()).toContain("Closed");
    expect(wrapper.emitted("closed")).toHaveLength(1);
  });

  it("disables the button and explains why while blocked", async () => {
    listAdminPeriods.mockResolvedValue([{ ...open, blockers: ["noRateConfigured"] }]);
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.find("button").attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("No electricity rate for 2026-09");
  });

  it("shows who closed it once closed", async () => {
    listAdminPeriods.mockResolvedValue([
      { ...open, closed_at: "2026-10-08T10:00:00Z", closed_by_name: "Head Admin", status: "closed" },
    ]);
    const wrapper = mountCard();
    await flushPromises();

    expect(wrapper.text()).toContain("by Head Admin");
    expect(wrapper.find("button").exists()).toBe(false);
  });
});

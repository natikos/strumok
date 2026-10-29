import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { getAuditLog, listAdminHouseholds } = vi.hoisted(() => ({
  getAuditLog: vi.fn(),
  listAdminHouseholds: vi.fn(),
}));

// The suite runs with isolate: false, so another file's mock of this module may
// already be cached; mock it late and import the component afterwards.
let AuditLogPanel: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => ({ getAuditLog, listAdminHouseholds }));
  AuditLogPanel = (await import("./AuditLogPanel.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

const entry = {
  action: "rateCreated",
  actor: { email: "a@x.io", first_name: "Head", id: 1, is_active: true, last_name: "Admin" },
  after: { day_rate_uah: "4.32" },
  before: null,
  created_at: "2030-01-05T10:00:00Z",
  entity_id: 1,
  entity_type: "electricity_rate",
  household_id: null,
  id: 7,
  period: "2030-01",
  reason: null,
};

function mountPanel() {
  return mount(AuditLogPanel, {
    global: {
      plugins: appPlugins(),
      components: { Button, InputText, Select },
      stubs: { ErrorState: true },
    },
  });
}

describe("AuditLogPanel", () => {
  beforeEach(() => {
    // PrimeVue's Select binds a matchMedia listener; jsdom doesn't implement it.
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        addEventListener: vi.fn(),
        matches: false,
        removeEventListener: vi.fn(),
      })
    );
    getAuditLog.mockReset();
    listAdminHouseholds.mockReset().mockResolvedValue([]);
  });

  it("renders who, what and the before → after summary", async () => {
    getAuditLog.mockResolvedValue({ items: [entry], next_cursor: null });
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain("Rate added");
    expect(wrapper.text()).toContain("by Head Admin");
    expect(wrapper.text()).toContain("— → day_rate_uah: 4.32");
  });

  it("loads the next page with the cursor and hides the button on the last page", async () => {
    getAuditLog
      .mockResolvedValueOnce({ items: [entry], next_cursor: 7 })
      .mockResolvedValueOnce({ items: [{ ...entry, id: 6 }], next_cursor: null });
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find(".audit-log__more").trigger("click");
    await flushPromises();

    expect(getAuditLog).toHaveBeenLastCalledWith({ cursor: 7 });
    expect(wrapper.findAll(".audit-entry")).toHaveLength(2);
    expect(wrapper.find(".audit-log__more").exists()).toBe(false);
  });

  it("shows the empty state", async () => {
    getAuditLog.mockResolvedValue({ items: [], next_cursor: null });
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain("No entries match these filters");
  });
});

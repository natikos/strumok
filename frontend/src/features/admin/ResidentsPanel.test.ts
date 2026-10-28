import { flushPromises, mount } from "@vue/test-utils";
import InputText from "primevue/inputtext";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { listAdminUsers, updateAdminUser, confirmRequire } = vi.hoisted(() => ({
  confirmRequire: vi.fn(),
  listAdminUsers: vi.fn(),
  updateAdminUser: vi.fn(),
}));

vi.mock("primevue/useconfirm", () => ({ useConfirm: () => ({ require: confirmRequire }) }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let ResidentsPanel: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => ({ listAdminUsers, updateAdminUser }));
  ResidentsPanel = (await import("./ResidentsPanel.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

const ada = {
  email: "ada@example.com",
  first_name: "Ada",
  household_count: 2,
  id: 1,
  is_active: true,
  is_admin: false,
  last_name: "Owner",
};
const bob = { ...ada, email: "bob@example.com", first_name: "Bob", household_count: 0, id: 2 };

function mountPanel() {
  return mount(ResidentsPanel, {
    global: { components: { InputText }, plugins: appPlugins(), stubs: { ErrorState: true, Menu: true, Button: true } },
  });
}

describe("ResidentsPanel", () => {
  beforeEach(() => {
    listAdminUsers.mockReset().mockResolvedValue([ada, bob]);
    updateAdminUser.mockReset();
    confirmRequire.mockReset();
  });

  it("filters by name or email", async () => {
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.text()).toContain("Ada");
    expect(wrapper.text()).toContain("Bob");

    await wrapper.find("input").setValue("bob@");

    expect(wrapper.text()).not.toContain("Ada");
    expect(wrapper.text()).toContain("Bob");
  });

  it("shows household count and status pills", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.findAll("tbody tr")[0]!.text()).toContain("2");
    expect(wrapper.text()).toContain("Active");
    expect(wrapper.text()).toContain("Resident");
  });
});

import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Select from "primevue/select";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { listAdminUsers, updateAdminUser, confirmRequire, inviteAdminUser, listAdminHouseholds, resendAdminInvite } = vi.hoisted(() => ({
  inviteAdminUser: vi.fn(),
  listAdminHouseholds: vi.fn(),
  resendAdminInvite: vi.fn(),
  confirmRequire: vi.fn(),
  listAdminUsers: vi.fn(),
  updateAdminUser: vi.fn(),
}));

vi.mock("primevue/usetoast", () => ({ useToast: () => ({ add: vi.fn() }) }));
vi.mock("primevue/useconfirm", () => ({ useConfirm: () => ({ require: confirmRequire }) }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let ResidentsPanel: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => ({
    inviteAdminUser,
    listAdminHouseholds,
    listAdminUsers,
    resendAdminInvite,
    updateAdminUser,
  }));
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
    global: { components: { Button, InputText, Message, Select }, plugins: appPlugins(), stubs: { ErrorState: true, Menu: true } },
  });
}

describe("ResidentsPanel", () => {
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
    listAdminUsers.mockReset().mockResolvedValue([ada, bob]);
    updateAdminUser.mockReset();
    inviteAdminUser.mockReset();
    listAdminHouseholds.mockReset().mockResolvedValue([]);
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

  it("invites a resident and offers the link to copy when the email didn't go out", async () => {
    inviteAdminUser.mockResolvedValue({
      email_sent: false,
      invite_link: "https://app/set-password?token=t",
      user: { ...ada, id: 9, email: "new@example.com" },
    });
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find(".residents__invite button").trigger("click");
    await flushPromises();
    const inputs = wrapper.findAll(".residents__invite-form input");
    await inputs[0]!.setValue("Nina");
    await inputs[1]!.setValue("Kovalenko");
    await inputs[2]!.setValue("new@example.com");
    await wrapper.find(".residents__invite-form").trigger("submit");
    await flushPromises();

    expect(inviteAdminUser).toHaveBeenCalledWith({
      email: "new@example.com",
      first_name: "Nina",
      language: "ua",
      last_name: "Kovalenko",
    });
    expect(wrapper.text()).toContain("Copy invite link");
  });
});

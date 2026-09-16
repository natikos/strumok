import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { AdminHouseholdOut, AdminUserSummaryOut } from "@shared/api/admin";

import AdminHouseholdAssignment from "./AdminHouseholdAssignment.vue";

const { listAdminUsers, listAdminHouseholds, assignAdminHouseholdOwner, createAdminHousehold } =
  vi.hoisted(() => ({
    assignAdminHouseholdOwner: vi.fn(),
    createAdminHousehold: vi.fn(),
    listAdminHouseholds: vi.fn(),
    listAdminUsers: vi.fn(),
  }));

vi.mock("@shared/api/admin", () => ({
  assignAdminHouseholdOwner,
  createAdminHousehold,
  listAdminHouseholds,
  listAdminUsers,
}));

const { confirmRequire } = vi.hoisted(() => ({
  confirmRequire: vi.fn(),
}));

vi.mock("primevue/useconfirm", () => ({
  useConfirm: () => ({ require: confirmRequire }),
}));

vi.mock("primevue/usetoast", () => ({
  useToast: () => ({ add: vi.fn() }),
}));

function makeUser(overrides: Partial<AdminUserSummaryOut> = {}): AdminUserSummaryOut {
  return {
    email: "resident@example.com",
    first_name: "Res",
    id: 1,
    is_active: true,
    last_name: "Ident",
    ...overrides,
  };
}

function makeHousehold(overrides: Partial<AdminHouseholdOut> = {}): AdminHouseholdOut {
  return {
    id: 1,
    is_active: true,
    name: "Plot 1",
    owner: null,
    user_id: null,
    ...overrides,
  };
}

async function mountForm() {
  const wrapper = mount(AdminHouseholdAssignment, {
    global: {
      components: { Button, InputText, Select },
      plugins: appPlugins(),
    },
  });
  await flushPromises();
  return wrapper;
}

describe("AdminHouseholdAssignment", () => {
  beforeEach(() => {
    // PrimeVue's Select binds a matchMedia listener for orientation changes;
    // jsdom doesn't implement matchMedia at all.
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        addEventListener: vi.fn(),
        matches: false,
        removeEventListener: vi.fn(),
      })
    );
    listAdminUsers.mockReset();
    listAdminHouseholds.mockReset();
    assignAdminHouseholdOwner.mockReset();
    createAdminHousehold.mockReset();
    confirmRequire.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("asks for confirmation before reassigning a household that already has a different owner", async () => {
    const currentOwner = makeUser({ email: "owner@example.com", id: 1, last_name: "Owner" });
    const newTarget = makeUser({ email: "target@example.com", id: 2, last_name: "Target" });
    const household = makeHousehold({ id: 10, owner: currentOwner, user_id: currentOwner.id });
    listAdminUsers.mockResolvedValue([currentOwner, newTarget]);
    listAdminHouseholds.mockResolvedValue([household]);

    const wrapper = await mountForm();

    await wrapper.findComponent(Select).setValue(household.id);
    const selects = wrapper.findAllComponents(Select);
    await selects[1]!.setValue(newTarget.id);
    await wrapper.findComponent(Button).trigger("click");
    await flushPromises();

    expect(confirmRequire).toHaveBeenCalledTimes(1);
    expect(assignAdminHouseholdOwner).not.toHaveBeenCalled();
  });

  it("submits directly without a confirmation dialog when the household is currently unowned", async () => {
    const targetUser = makeUser({ email: "target2@example.com", id: 3 });
    const unownedHousehold = makeHousehold({ id: 20, owner: null, user_id: null });
    listAdminUsers.mockResolvedValue([targetUser]);
    listAdminHouseholds.mockResolvedValue([unownedHousehold]);
    assignAdminHouseholdOwner.mockResolvedValue({
      ...unownedHousehold,
      owner: targetUser,
      user_id: targetUser.id,
    });

    const wrapper = await mountForm();

    const selects = wrapper.findAllComponents(Select);
    await selects[0]!.setValue(unownedHousehold.id);
    await selects[1]!.setValue(targetUser.id);
    await wrapper.findComponent(Button).trigger("click");
    await flushPromises();

    expect(confirmRequire).not.toHaveBeenCalled();
    expect(assignAdminHouseholdOwner).toHaveBeenCalledWith(unownedHousehold.id, {
      confirm_reassignment: false,
      user_id: targetUser.id,
    });
  });
});

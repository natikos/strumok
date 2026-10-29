import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { AdminHouseholdOut, AdminUserSummaryOut } from "@shared/api/admin";
import { ApiError } from "@shared/api/client";

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

function fillHandover(wrapper: Awaited<ReturnType<typeof mountForm>>) {
  const numbers = wrapper.findAllComponents(InputNumber);
  numbers[0]!.vm.$emit("update:modelValue", 500);
  numbers[1]!.vm.$emit("update:modelValue", 200);
}

async function mountForm() {
  const wrapper = mount(AdminHouseholdAssignment, {
    global: {
      components: { Button, InputNumber, InputText, Select },
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
    fillHandover(wrapper);
    await wrapper.find(".admin-assignment__submit").trigger("click");
    await flushPromises();

    expect(confirmRequire).toHaveBeenCalledTimes(1);
    expect(assignAdminHouseholdOwner).not.toHaveBeenCalled();
  });

  it("will not transfer a household without the handover meter values", async () => {
    const currentOwner = makeUser({ id: 1 });
    const newTarget = makeUser({ email: "t@example.com", id: 2 });
    const household = makeHousehold({ id: 10, owner: currentOwner, user_id: currentOwner.id });
    listAdminUsers.mockResolvedValue([currentOwner, newTarget]);
    listAdminHouseholds.mockResolvedValue([household]);

    const wrapper = await mountForm();
    await wrapper.findComponent(Select).setValue(household.id);
    await wrapper.findAllComponents(Select)[1]!.setValue(newTarget.id);
    await wrapper.find(".admin-assignment__submit").trigger("click");
    await flushPromises();

    expect(confirmRequire).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Enter both meter values at the handover");
  });

  it("sends the handover values and asks again when the previous owner owes money", async () => {
    const currentOwner = makeUser({ id: 1 });
    const newTarget = makeUser({ email: "t@example.com", id: 2 });
    const household = makeHousehold({ id: 10, owner: currentOwner, user_id: currentOwner.id });
    listAdminUsers.mockResolvedValue([currentOwner, newTarget]);
    listAdminHouseholds.mockResolvedValue([household]);
    assignAdminHouseholdOwner
      .mockRejectedValueOnce(new ApiError("householdHasOutstandingBalance", 409))
      .mockResolvedValueOnce({ ...household, owner: newTarget, user_id: newTarget.id });

    const wrapper = await mountForm();
    await wrapper.findComponent(Select).setValue(household.id);
    await wrapper.findAllComponents(Select)[1]!.setValue(newTarget.id);
    fillHandover(wrapper);
    await wrapper.find(".admin-assignment__submit").trigger("click");
    await flushPromises();
    confirmRequire.mock.calls[0]![0].accept();
    await flushPromises();
    expect(assignAdminHouseholdOwner).toHaveBeenLastCalledWith(10, {
      acknowledge_balance: false,
      confirm_reassignment: true,
      handover_day_meter_value: "500",
      handover_night_meter_value: "200",
      user_id: 2,
    });

    confirmRequire.mock.calls[1]![0].accept();
    await flushPromises();

    expect(assignAdminHouseholdOwner).toHaveBeenLastCalledWith(10, {
      acknowledge_balance: true,
      confirm_reassignment: true,
      handover_day_meter_value: "500",
      handover_night_meter_value: "200",
      user_id: 2,
    });
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
    await wrapper.find(".admin-assignment__submit").trigger("click");
    await flushPromises();

    expect(confirmRequire).not.toHaveBeenCalled();
    expect(assignAdminHouseholdOwner).toHaveBeenCalledWith(unownedHousehold.id, {
      acknowledge_balance: false,
      confirm_reassignment: false,
      user_id: targetUser.id,
    });
  });

  it("asks for the handover meters when an unowned plot had an earlier owner", async () => {
    const targetUser = makeUser({ id: 3 });
    const household = makeHousehold({ id: 20 });
    listAdminUsers.mockResolvedValue([targetUser]);
    listAdminHouseholds.mockResolvedValue([household]);
    assignAdminHouseholdOwner
      .mockRejectedValueOnce(new ApiError("handoverReadingRequired", 409))
      .mockRejectedValueOnce(new ApiError("householdHasOutstandingBalance", 409))
      .mockResolvedValueOnce({ ...household, owner: targetUser, user_id: targetUser.id });

    const wrapper = await mountForm();
    const selects = wrapper.findAllComponents(Select);
    await selects[0]!.setValue(household.id);
    await selects[1]!.setValue(targetUser.id);
    expect(wrapper.findAllComponents(InputNumber)).toHaveLength(0);

    await wrapper.find(".admin-assignment__submit").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Enter both meter values at the handover");

    fillHandover(wrapper);
    await wrapper.find(".admin-assignment__submit").trigger("click");
    await flushPromises();
    expect(confirmRequire.mock.calls[0]![0].message).toContain("The previous owner still owes");
    confirmRequire.mock.calls[0]![0].accept();
    await flushPromises();

    expect(assignAdminHouseholdOwner).toHaveBeenLastCalledWith(20, {
      acknowledge_balance: true,
      confirm_reassignment: true,
      handover_day_meter_value: "500",
      handover_night_meter_value: "200",
      user_id: 3,
    });
  });

  it("sends the starting meter values when creating a new household", async () => {
    const owner = makeUser({ email: "new@example.com", id: 5 });
    listAdminUsers.mockResolvedValue([owner]);
    listAdminHouseholds.mockResolvedValue([]);
    createAdminHousehold.mockResolvedValue(makeHousehold({ id: 30, name: "Plot 30" }));

    const wrapper = await mountForm();

    await wrapper.find("#admin-household-name").setValue("Plot 30");
    const numbers = wrapper.findAllComponents(InputNumber);
    numbers[0]!.vm.$emit("update:modelValue", 250.5);
    numbers[1]!.vm.$emit("update:modelValue", 120);
    await wrapper.findAllComponents(Select)[1]!.setValue(owner.id);
    await wrapper.find(".admin-assignment__submit").trigger("click");
    await flushPromises();

    expect(createAdminHousehold).toHaveBeenCalledWith({
      name: "Plot 30",
      starting_day_meter_value: "250.5",
      starting_night_meter_value: "120",
      user_id: owner.id,
    });
  });

  it("refuses a lone starting value", async () => {
    const owner = makeUser({ email: "new2@example.com", id: 6 });
    listAdminUsers.mockResolvedValue([owner]);
    listAdminHouseholds.mockResolvedValue([]);

    const wrapper = await mountForm();

    await wrapper.find("#admin-household-name").setValue("Plot 31");
    wrapper.findAllComponents(InputNumber)[0]!.vm.$emit("update:modelValue", 10);
    await wrapper.findAllComponents(Select)[1]!.setValue(owner.id);
    await wrapper.find(".admin-assignment__submit").trigger("click");
    await flushPromises();

    expect(createAdminHousehold).not.toHaveBeenCalled();
  });
});

import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { confirmRequire, recordMeterChange, toastAdd } = vi.hoisted(() => ({
  confirmRequire: vi.fn(),
  recordMeterChange: vi.fn(),
  toastAdd: vi.fn(),
}));

vi.mock("primevue/useconfirm", () => ({ useConfirm: () => ({ require: confirmRequire }) }));
vi.mock("primevue/usetoast", () => ({ useToast: () => ({ add: toastAdd }) }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let MeterChangeForm: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => ({ recordMeterChange }));
  MeterChangeForm = (await import("./MeterChangeForm.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

function mountForm() {
  return mount(MeterChangeForm, {
    props: { household: { id: 4, name: "Plot 4" }, period: "2026-07" },
    global: { components: { Button, InputNumber, InputText }, plugins: appPlugins() },
  });
}

async function fill(wrapper: ReturnType<typeof mountForm>) {
  const numbers = wrapper.findAllComponents(InputNumber);
  const values = [130, 60, 0, 0];
  for (const [index, value] of values.entries()) {
    numbers[index]!.vm.$emit("update:modelValue", value);
  }
  await wrapper.find("input[placeholder='Reason (required)']").setValue("swapped by the utility");
}

describe("MeterChangeForm", () => {
  beforeEach(() => {
    confirmRequire.mockReset();
    recordMeterChange.mockReset();
    toastAdd.mockReset();
  });

  it("cannot be submitted until all four values and a reason are in", async () => {
    const wrapper = mountForm();

    expect(wrapper.findAllComponents(Button)[0]!.attributes("disabled")).toBeDefined();

    await fill(wrapper);

    expect(wrapper.findAllComponents(Button)[0]!.attributes("disabled")).toBeUndefined();
  });

  it("asks for confirmation, records the change and shows the computed usage", async () => {
    recordMeterChange.mockResolvedValue({ day_usage_kwh: "50.00", night_usage_kwh: "15.00" });
    const wrapper = mountForm();
    await fill(wrapper);

    await wrapper.findAllComponents(Button)[0]!.trigger("click");
    expect(recordMeterChange).not.toHaveBeenCalled();
    confirmRequire.mock.calls[0]![0].accept();
    await flushPromises();

    expect(recordMeterChange).toHaveBeenCalledWith(4, {
      new_start_day: "0",
      new_start_night: "0",
      old_final_day: "130",
      old_final_night: "60",
      period: "2026-07",
      reason: "swapped by the utility",
    });
    expect(toastAdd.mock.calls[0]![0].detail).toContain("50");
    expect(wrapper.emitted("changed")).toHaveLength(1);
  });
});

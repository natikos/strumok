import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const { confirmRequire, deleteElectricityRate, updateElectricityRate } = vi.hoisted(() => ({
  confirmRequire: vi.fn(),
  deleteElectricityRate: vi.fn(),
  updateElectricityRate: vi.fn(),
}));

vi.mock("primevue/useconfirm", () => ({ useConfirm: () => ({ require: confirmRequire }) }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let RateEditor: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/electricity-rates", () => ({
    deleteElectricityRate,
    updateElectricityRate,
  }));
  RateEditor = (await import("./RateEditor.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/electricity-rates");
  vi.resetModules();
});

const rate = {
  day_rate_uah: "4.3200",
  effective_from: "2026-01",
  history: [],
  id: 3,
  night_rate_uah: "2.1600",
  used_by_closed_periods: [] as string[],
};

function mountEditor(overrides: Partial<typeof rate> = {}) {
  return mount(RateEditor, {
    props: { rate: { ...rate, ...overrides } },
    global: { components: { Button, InputNumber, InputText }, plugins: appPlugins() },
  });
}

describe("RateEditor", () => {
  beforeEach(() => {
    confirmRequire.mockReset();
    updateElectricityRate.mockReset();
    deleteElectricityRate.mockReset();
  });

  it("is read-only with an explanation when a closed period used the rate", async () => {
    const wrapper = mountEditor({ used_by_closed_periods: ["2026-02", "2026-03"] });

    await wrapper.find(".rate-editor__toggle").trigger("click");

    expect(wrapper.text()).toContain("used to bill 2026-02, 2026-03");
    expect(wrapper.find(".rate-editor__actions").exists()).toBe(false);
  });

  it("confirms before deleting and passes the reason", async () => {
    deleteElectricityRate.mockResolvedValue(undefined);
    const wrapper = mountEditor();

    await wrapper.find(".rate-editor__toggle").trigger("click");
    await wrapper.find("input[placeholder='Reason (optional)']").setValue("duplicate");
    await wrapper.findAll(".rate-editor__actions button")[1]!.trigger("click");

    expect(deleteElectricityRate).not.toHaveBeenCalled();
    (confirmRequire.mock.calls[0]![0] as { accept: () => void }).accept();
    await flushPromises();

    expect(deleteElectricityRate).toHaveBeenCalledWith(3, "duplicate");
    expect(wrapper.emitted("changed")).toHaveLength(1);
  });
});

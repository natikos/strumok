import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { OpeningBalanceOut } from "@shared/api/admin";
import type { Component } from "vue";

const { correctOpeningBalance, getOpeningBalance, setOpeningBalance } = vi.hoisted(() => ({
  correctOpeningBalance: vi.fn(),
  getOpeningBalance: vi.fn(),
  setOpeningBalance: vi.fn(),
}));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let OpeningBalanceEditor: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => ({
    correctOpeningBalance,
    getOpeningBalance,
    setOpeningBalance,
  }));
  OpeningBalanceEditor = (await import("./OpeningBalanceEditor.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

const opening: OpeningBalanceOut = {
  amount_uah: "-300.00",
  as_of: "2024-12-01",
  corrections: [],
  created_at: "2024-12-01T00:00:00Z",
  effective_amount_uah: "-300.00",
  household_id: 7,
  note: null,
};

async function mountEditor() {
  const wrapper = mount(OpeningBalanceEditor, {
    global: {
      components: { Button, InputNumber, InputText },
      plugins: appPlugins(),
      stubs: { Skeleton: true },
    },
    props: { householdId: 7 },
  });
  await flushPromises();
  return wrapper;
}

describe("OpeningBalanceEditor", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("posts a signed correction with a trimmed reason and reports the change", async () => {
    getOpeningBalance.mockResolvedValue(opening);
    correctOpeningBalance.mockResolvedValue({
      ...opening,
      corrections: [{ amount_uah: "600.00", created_at: "", id: 1, reason: "sign flipped" }],
      effective_amount_uah: "300.00",
    });
    const wrapper = await mountEditor();

    const input = wrapper.find("#opening-correction-7");
    await input.setValue("600");
    await input.trigger("blur");
    await wrapper.find("#opening-reason-7").setValue("  sign flipped ");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(correctOpeningBalance).toHaveBeenCalledWith(7, {
      amount_uah: "600",
      reason: "sign flipped",
    });
    expect(wrapper.emitted("changed")).toHaveLength(1);
    expect(wrapper.text()).toContain("sign flipped");
  });

  it("offers to set an opening balance when none exists", async () => {
    getOpeningBalance.mockResolvedValue(null);
    const wrapper = await mountEditor();

    expect(wrapper.find("#opening-amount-7").exists()).toBe(true);
    expect(wrapper.find("#opening-correction-7").exists()).toBe(false);
  });
});

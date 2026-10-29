import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

import RestatementPreview from "./RestatementPreview.vue";

const { confirmRequire, getPeriodReconciliation, putPeriodBill, restatePeriod } = vi.hoisted(
  () => ({
    restatePeriod: vi.fn(),
    confirmRequire: vi.fn(),
    getPeriodReconciliation: vi.fn(),
    putPeriodBill: vi.fn(),
  })
);

vi.mock("primevue/useconfirm", () => ({ useConfirm: () => ({ require: confirmRequire }) }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let ReconciliationPanel: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => ({ getPeriodReconciliation, putPeriodBill, restatePeriod }));
  ReconciliationPanel = (await import("./ReconciliationPanel.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

const line = {
  household_id: 1,
  household_name: "Plot 1",
  is_estimated: false,
  loss_share_uah: "25.00",
  penalty_uah: "0.00",
  tariff_uah: "100.00",
  total_uah: "125.00",
  usage_kwh: "100.00",
  usage_share_percent: "25.00",
};

const base = {
  bill_day_kwh: "300.00",
  bill_night_kwh: "100.00",
  bill_total_uah: "500.00",
  closed_at: null,
  kwh_loss: "0.00",
  kwh_loss_percent: "0.00",
  lines: [line],
  loss_percent: "20.00",
  loss_uah: "100.00",
  period: "2026-09",
  remainder_household_names: ["Plot 1"],
  shares_total_uah: "500.00",
  status: "open",
  total_tariff_uah: "400.00",
  total_usage_kwh: "400.00",
  variance_uah: "0.00",
};

function mountPanel() {
  return mount(ReconciliationPanel, {
    props: { period: "2026-09" },
    global: {
      components: { Button, InputNumber, InputText, RestatementPreview },
      plugins: appPlugins(),
      stubs: { ErrorState: true, Skeleton: true },
    },
  });
}

describe("ReconciliationPanel", () => {
  beforeEach(() => {
    confirmRequire.mockReset();
    putPeriodBill.mockReset();
    getPeriodReconciliation.mockReset().mockResolvedValue(base);
  });

  it("leads with the result line and names the rounding-remainder household", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find(".reconciliation__result").text()).toContain("Shares add up to the bill");
    expect(wrapper.text()).toContain("Rounding remainder (kopecks) went to: Plot 1");
    expect(wrapper.text()).toContain("Plot 1");
  });

  it("states a shortfall in words, not just color", async () => {
    getPeriodReconciliation.mockResolvedValue({ ...base, variance_uah: "-5.00" });
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find(".reconciliation__result").text()).toContain("(shortfall)");
  });

  it("shows a prompt and dashes when the bill is missing", async () => {
    getPeriodReconciliation.mockResolvedValue({
      ...base,
      bill_day_kwh: null,
      bill_night_kwh: null,
      bill_total_uah: null,
      loss_uah: null,
      variance_uah: null,
    });
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find(".reconciliation__result").text()).toContain("Bill not entered yet");
    expect(wrapper.find("tbody tr").text()).toContain("—");
  });

  it("turns a closed period's bill entry into a correction that leads to a preview", async () => {
    getPeriodReconciliation.mockResolvedValue({
      ...base,
      closed_at: "2026-10-08T10:00:00Z",
      status: "closed",
    });
    restatePeriod.mockResolvedValue({
      affected_periods: ["2026-09"],
      is_zero_sum: false,
      lines: [],
      posted_in_period: "2026-10",
      restatement_id: null,
      total_delta_uah: "0.00",
    });
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain("This period is closed");
    expect(wrapper.find(".reconciliation__card button").attributes("disabled")).toBeDefined();

    wrapper.findAllComponents(InputNumber)[2]!.vm.$emit("update:modelValue", 600);
    await flushPromises();
    await wrapper.find(".reconciliation__card button").trigger("click");
    await flushPromises();

    expect(restatePeriod).toHaveBeenCalledWith(
      "2026-09",
      { bill_total_uah: "600" },
      { dryRun: true, reason: "" }
    );
  });

  it("asks before replacing an already-entered bill", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find(".reconciliation__card button").trigger("click");

    expect(confirmRequire).toHaveBeenCalledTimes(1);
    expect(putPeriodBill).not.toHaveBeenCalled();
  });
});

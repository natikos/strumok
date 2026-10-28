import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Skeleton from "primevue/skeleton";
import { describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";

import RestatementPreview from "./RestatementPreview.vue";

const result = (overrides = {}) => ({
  affected_periods: ["2026-09"],
  is_zero_sum: false,
  lines: [
    {
      after_uah: "150.00",
      before_uah: "125.00",
      delta_uah: "25.00",
      household_id: 1,
      household_name: "Plot 1",
      period: "2026-09",
    },
    {
      after_uah: "300.00",
      before_uah: "312.40",
      delta_uah: "-12.40",
      household_id: 2,
      household_name: "Plot 2",
      period: "2026-09",
    },
  ],
  posted_in_period: "2026-10",
  restatement_id: null,
  total_delta_uah: "12.60",
  ...overrides,
});

function mountPreview(request: ReturnType<typeof vi.fn>) {
  return mount(RestatementPreview, {
    props: { request: request as unknown as (o: { dryRun: boolean; reason: string }) => Promise<ReturnType<typeof result>> },
    global: { components: { Button, InputText, Skeleton }, plugins: appPlugins() },
  });
}

describe("RestatementPreview", () => {
  it("lists each household with a signed delta labelled in words", async () => {
    const wrapper = mountPreview(vi.fn().mockResolvedValue(result()));
    await flushPromises();

    const cards = wrapper.findAll(".restatement__card");
    expect(cards).toHaveLength(2);
    expect(cards[0]!.text()).toContain("+");
    expect(cards[0]!.text()).toContain("extra charge");
    expect(cards[1]!.text()).toContain("refund");
    expect(wrapper.text()).toContain("2 household(s) across 1 period(s)");
  });

  it("keeps posting disabled with a hint until a reason is entered", async () => {
    const request = vi.fn().mockResolvedValue(result());
    const wrapper = mountPreview(request);
    await flushPromises();

    const confirm = wrapper.find(".restatement__actions button");
    expect(confirm.attributes("disabled")).toBeDefined();
    expect(confirm.attributes("aria-disabled")).toBe("true");
    expect(wrapper.text()).toContain("Enter a reason to continue");

    await wrapper.find("input").setValue("typo in the bill");
    expect(wrapper.find(".restatement__actions button").attributes("disabled")).toBeUndefined();

    request.mockResolvedValue(result({ restatement_id: 7 }));
    await wrapper.find(".restatement__actions button").trigger("click");
    await flushPromises();

    expect(request).toHaveBeenLastCalledWith({ dryRun: false, reason: "typo in the bill" });
    expect(wrapper.emitted("posted")).toHaveLength(1);
  });

  it("says a zero-sum correction only moves money between tariff and loss share", async () => {
    const wrapper = mountPreview(
      vi.fn().mockResolvedValue(result({ is_zero_sum: true, lines: [], total_delta_uah: "0.00" }))
    );
    await flushPromises();

    expect(wrapper.text()).toContain("nets to zero");
    expect(wrapper.text()).toContain("No household's amount changes");
  });
});

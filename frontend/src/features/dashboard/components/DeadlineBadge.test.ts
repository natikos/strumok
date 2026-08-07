import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mountWithPlugins } from "@/shared/testing/mount";
import type { MeterReadingOut } from "@shared/api/meter-readings";

import DeadlineBadge from "./DeadlineBadge.vue";

function makeReading(overrides: Partial<MeterReadingOut> = {}): MeterReadingOut {
  return {
    id: 1,
    household_id: 1,
    submitted_by_user_id: 1,
    period: "2026-06",
    day_meter_value: "120.00",
    night_meter_value: "60.00",
    day_usage_kwh: "10.00",
    night_usage_kwh: "5.00",
    amount_charged_uah: "0.00",
    submitted_at: "2026-06-02T09:00:00.000Z",
    ...overrides,
  };
}

describe("DeadlineBadge", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shows the due state with a clock icon when nothing is submitted and within the window", () => {
    vi.setSystemTime(new Date(2026, 5, 3));
    const wrapper = mountWithPlugins(DeadlineBadge, { props: { reading: null } });

    expect(wrapper.text()).toContain("Due");
    expect(wrapper.find(".pi-clock").exists()).toBe(true);
    expect(wrapper.classes()).toContain("deadline-badge--due");
  });

  it("shows the overdue state with a times-circle icon when nothing is submitted past the window", () => {
    vi.setSystemTime(new Date(2026, 5, 20));
    const wrapper = mountWithPlugins(DeadlineBadge, { props: { reading: undefined } });

    expect(wrapper.text()).toContain("Overdue");
    expect(wrapper.find(".pi-times-circle").exists()).toBe(true);
    expect(wrapper.classes()).toContain("deadline-badge--overdue");
  });

  it("shows the submitted state with a check-circle icon for an on-time reading", () => {
    vi.setSystemTime(new Date(2026, 5, 20));
    const reading = makeReading({ submitted_at: new Date(2026, 5, 3, 9, 0).toISOString() });
    const wrapper = mountWithPlugins(DeadlineBadge, { props: { reading } });

    expect(wrapper.text()).toContain("Submitted");
    expect(wrapper.text()).not.toContain("Submitted late");
    expect(wrapper.find(".pi-check-circle").exists()).toBe(true);
    expect(wrapper.classes()).toContain("deadline-badge--submitted");
  });

  it("shows the submitted-late state with a warning icon for a late reading", () => {
    vi.setSystemTime(new Date(2026, 5, 20));
    const reading = makeReading({ submitted_at: new Date(2026, 5, 10, 9, 0).toISOString() });
    const wrapper = mountWithPlugins(DeadlineBadge, { props: { reading } });

    expect(wrapper.text()).toContain("Submitted late");
    expect(wrapper.find(".pi-exclamation-triangle").exists()).toBe(true);
    expect(wrapper.classes()).toContain("deadline-badge--submitted-late");
  });
});

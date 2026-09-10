import Skeleton from "primevue/skeleton";
import { describe, expect, it } from "vitest";

import type { YearOverYear } from "@/features/dashboard/composables/useUsageInsights";
import { mountWithPlugins } from "@/shared/testing/mount";

import YearOverYearCard from "./YearOverYearCard.vue";

function makeComparison(overrides: Partial<YearOverYear> = {}): YearOverYear {
  return {
    monthIndex: 5,
    monthLong: "June",
    current: 150,
    previous: 200,
    deltaKwh: -50,
    deltaPercent: -25,
    direction: "down",
    deltaUah: null,
    ...overrides,
  };
}

describe("YearOverYearCard", () => {
  it("renders two comparison rows with an image role and aria-labels carrying both year and value", () => {
    const wrapper = mountWithPlugins(YearOverYearCard, {
      props: { comparison: makeComparison(), emptyMonth: "June", emptyYear: 2026 },
      global: { components: { Skeleton } },
    });

    const rows = wrapper.findAll('[role="img"]');
    expect(rows).toHaveLength(2);
    rows.forEach((row) => {
      const label = row.attributes("aria-label");
      expect(label).toBeTruthy();
      expect(label).toMatch(/kWh/);
    });
  });

  it("shows the unavailable message with the missing month and year when no comparison exists", () => {
    const wrapper = mountWithPlugins(YearOverYearCard, {
      props: { comparison: null, emptyMonth: "January", emptyYear: 2025 },
      global: { components: { Skeleton } },
    });

    expect(wrapper.find(".yoy-card__empty").exists()).toBe(true);
    expect(wrapper.text()).toContain("January 2025");
    expect(wrapper.findAll('[role="img"]')).toHaveLength(0);
    expect(wrapper.classes()).toContain("yoy-card--unavailable");
  });

  it("renders skeleton placeholders while loading, without rows or the empty message", () => {
    const wrapper = mountWithPlugins(YearOverYearCard, {
      props: { comparison: null, emptyMonth: "June", emptyYear: 2026, isLoading: true },
      global: { components: { Skeleton } },
    });

    expect(wrapper.findAllComponents(Skeleton).length).toBeGreaterThan(0);
    expect(wrapper.find(".yoy-card__empty").exists()).toBe(false);
    expect(wrapper.findAll('[role="img"]')).toHaveLength(0);
  });

  it("uses the decrease treatment on the delta pill when usage went down", () => {
    const wrapper = mountWithPlugins(YearOverYearCard, {
      props: {
        comparison: makeComparison({ direction: "down", deltaKwh: -50 }),
        emptyMonth: "June",
        emptyYear: 2026,
      },
      global: { components: { Skeleton } },
    });

    const pill = wrapper.find(".yoy-card__pill");
    expect(pill.classes()).toContain("yoy-card__pill--down");
    expect(wrapper.find(".pi-arrow-down").exists()).toBe(true);
    expect(pill.text()).toContain("50");
    expect(pill.text()).toContain("kWh");
  });

  it("uses the increase treatment on the delta pill when usage went up", () => {
    const wrapper = mountWithPlugins(YearOverYearCard, {
      props: {
        comparison: makeComparison({ direction: "up", deltaKwh: 50, current: 200, previous: 150 }),
        emptyMonth: "June",
        emptyYear: 2026,
      },
      global: { components: { Skeleton } },
    });

    const pill = wrapper.find(".yoy-card__pill");
    expect(pill.classes()).toContain("yoy-card__pill--up");
    expect(wrapper.find(".pi-arrow-up").exists()).toBe(true);
    expect(pill.text()).toContain("50");
    expect(pill.text()).toContain("kWh");
  });
});

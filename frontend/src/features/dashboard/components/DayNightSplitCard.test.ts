import Skeleton from "primevue/skeleton";
import { describe, expect, it } from "vitest";

import type { DayNightSplit } from "@/features/dashboard/composables/useUsageInsights";
import { mountWithPlugins } from "@/shared/testing/mount";

import DayNightSplitCard from "./DayNightSplitCard.vue";

const split: DayNightSplit = {
  dayKwh: 82.5,
  nightKwh: 27.5,
  dayPct: 75,
  nightPct: 25,
};

describe("DayNightSplitCard", () => {
  it("renders the bar and day/night rows with values and percentages when data is available", () => {
    const wrapper = mountWithPlugins(DayNightSplitCard, {
      props: { split },
      global: { components: { Skeleton } },
    });

    expect(wrapper.find('[role="img"]').exists()).toBe(true);
    expect(wrapper.findAll(".split-card__row")).toHaveLength(2);
    expect(wrapper.find(".split-card__empty").exists()).toBe(false);
  });

  it("shows an empty state instead of a bar when split data is unavailable", () => {
    const wrapper = mountWithPlugins(DayNightSplitCard, {
      props: { split: null },
      global: { components: { Skeleton } },
    });

    expect(wrapper.find(".split-card__empty").exists()).toBe(true);
    expect(wrapper.find('[role="img"]').exists()).toBe(false);
    expect(wrapper.findAll(".split-card__row")).toHaveLength(0);
  });

  it("renders skeleton placeholders while loading, hiding both the bar and the empty state", () => {
    const wrapper = mountWithPlugins(DayNightSplitCard, {
      props: { split: null, isLoading: true },
      global: { components: { Skeleton } },
    });

    expect(wrapper.findAllComponents(Skeleton).length).toBeGreaterThan(0);
    expect(wrapper.find('[role="img"]').exists()).toBe(false);
    expect(wrapper.find(".split-card__empty").exists()).toBe(false);
  });

  it("carries both day and night values with units in the bar's aria-label", () => {
    const wrapper = mountWithPlugins(DayNightSplitCard, {
      props: { split },
      global: { components: { Skeleton } },
    });

    const label = wrapper.find('[role="img"]').attributes("aria-label");
    expect(label).toContain("82.5 kWh");
    expect(label).toContain("27.5 kWh");
  });

  it("shows a unit on the day and night row values", () => {
    const wrapper = mountWithPlugins(DayNightSplitCard, {
      props: { split },
      global: { components: { Skeleton } },
    });

    const values = wrapper.findAll(".split-card__value").map((el) => el.text());
    expect(values).toHaveLength(2);
    values.forEach((text) => expect(text).toContain("kWh"));
  });

  it("emits view-history when the history link is clicked", async () => {
    const wrapper = mountWithPlugins(DayNightSplitCard, {
      props: { split },
      global: { components: { Skeleton } },
    });

    await wrapper.find(".split-card__link").trigger("click");
    expect(wrapper.emitted("view-history")).toHaveLength(1);
  });
});

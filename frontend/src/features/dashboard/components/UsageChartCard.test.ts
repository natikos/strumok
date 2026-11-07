import Skeleton from "primevue/skeleton";
import { describe, expect, it } from "vitest";

import type { TrendSeries } from "@/features/dashboard/composables/useUsageInsights";
import { mountWithPlugins } from "@/shared/testing/mount";

import UsageChartCard from "./UsageChartCard.vue";

const series: TrendSeries = {
  labels: ["Nov", "Dec", "Jan"],
  fullLabels: ["November 2025", "December 2025", "January 2026"],
  day: [10, null, 30],
  night: [5, null, 12],
  presentCount: 2,
};

describe("UsageChartCard", () => {
  it("keeps its container aria-busy with a skeleton while loading and drops both once loaded", async () => {
    const wrapper = mountWithPlugins(UsageChartCard, {
      props: { series, isLoading: true },
      global: { stubs: { Chart: true } },
    });
    expect(wrapper.attributes("aria-busy")).toBe("true");
    expect(wrapper.findAllComponents(Skeleton).length).toBeGreaterThan(0);

    await wrapper.setProps({ isLoading: false });

    expect(wrapper.attributes("aria-busy")).not.toBe("true");
    expect(wrapper.findAllComponents(Skeleton)).toHaveLength(0);
  });
});

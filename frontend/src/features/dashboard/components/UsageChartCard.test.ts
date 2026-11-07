import { describe, it } from "vitest";

import type { TrendSeries } from "@/features/dashboard/composables/useUsageInsights";
import { expectLoaded, expectLoading } from "@/shared/testing/loading";
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
    expectLoading(wrapper);

    await wrapper.setProps({ isLoading: false } as never);

    expectLoaded(wrapper);
  });
});

import Skeleton from "primevue/skeleton";
import { describe, expect, it } from "vitest";

import type {
  DaysIntoPeriod,
  MomChange,
  MonthlyAverage,
  PeriodUsage,
} from "@/features/dashboard/composables/useUsageInsights";
import { mountWithPlugins } from "@/shared/testing/mount";

import StatTilesCard from "./StatTilesCard.vue";

const daysIntoPeriod: DaysIntoPeriod = { day: 12, daysInMonth: 30, monthIndex: 5 };

const lastPeriod: PeriodUsage = {
  period: "2026-06",
  monthLabel: "Jun",
  monthLong: "June",
  monthIndex: 5,
  dayKwh: 120.5,
  nightKwh: 45.25,
  totalKwh: 165.75,
  chargedUah: null,
};

const momChange: MomChange = {
  percent: 12.3,
  from: 100,
  to: 112.3,
  direction: "up",
  deltaUah: null,
};

const monthlyAverage: MonthlyAverage = { averageKwh: 150.4, periodCount: 8 };

interface MountOverrides {
  lastPeriod?: PeriodUsage | null;
  momChange?: MomChange | null;
  daysIntoPeriod?: DaysIntoPeriod;
  monthlyAverage?: MonthlyAverage | null;
  missedPeriods?: number;
  isLoading?: boolean;
}

function mountCard(overrides: MountOverrides = {}) {
  return mountWithPlugins(StatTilesCard, {
    props: {
      lastPeriod,
      momChange,
      daysIntoPeriod,
      monthlyAverage,
      ...overrides,
    },
    global: { components: { Skeleton } },
  });
}

describe("StatTilesCard", () => {
  it("always renders exactly 3 tiles", () => {
    const wrapper = mountCard();
    expect(wrapper.findAll(".stat-tile")).toHaveLength(3);
  });

  it("renders skeleton placeholders instead of tiles while loading", () => {
    const wrapper = mountCard({ isLoading: true });

    expect(wrapper.findAllComponents(Skeleton).length).toBeGreaterThan(0);
    expect(wrapper.findAll(".stat-tile")).toHaveLength(0);
  });

  describe("overdue swaps the comparison tile for missed periods", () => {
    it("shows a missed-periods count instead of the vs-month comparison", () => {
      const wrapper = mountCard({ missedPeriods: 2 });

      expect(wrapper.text()).toContain("Missed periods");
      expect(wrapper.text()).toContain("2");
      expect(wrapper.text()).not.toContain("vs ");
    });
  });

  describe("empty states render dashes, not raw nulls", () => {
    it("shows an empty last-period tile when there is no submitted history yet", () => {
      const wrapper = mountCard({ lastPeriod: null });

      const tiles = wrapper.findAll(".stat-tile");
      expect(tiles[0]?.classes()).toContain("stat-tile--empty");
      expect(tiles[0]?.text()).toContain("—");
      expect(tiles[0]?.text()).not.toContain("NaN");
    });

    it("shows an empty comparison tile when momChange is null and nothing is missed", () => {
      const wrapper = mountCard({ momChange: null, missedPeriods: 0 });

      const tiles = wrapper.findAll(".stat-tile");
      expect(tiles[1]?.classes()).toContain("stat-tile--empty");
      expect(tiles[1]?.text()).toContain("—");
    });

    it("shows an empty average tile when monthlyAverage is null", () => {
      const wrapper = mountCard({ monthlyAverage: null });

      const tiles = wrapper.findAll(".stat-tile");
      expect(tiles[2]?.classes()).toContain("stat-tile--empty");
      expect(tiles[2]?.text()).toContain("—");
    });
  });

  describe("month-over-month direction", () => {
    it("shows a down arrow and the down styling class when usage decreased", () => {
      const wrapper = mountCard({
        momChange: { percent: -10, from: 100, to: 90, direction: "down", deltaUah: null },
      });

      expect(wrapper.find(".pi-arrow-down").exists()).toBe(true);
      expect(wrapper.find(".pi-arrow-up").exists()).toBe(false);
      expect(wrapper.find(".stat-tile__value--down").exists()).toBe(true);
    });

    it("shows an up arrow and the up styling class when usage increased", () => {
      const wrapper = mountCard({
        momChange: { percent: 10, from: 100, to: 110, direction: "up", deltaUah: null },
      });

      expect(wrapper.find(".pi-arrow-up").exists()).toBe(true);
      expect(wrapper.find(".pi-arrow-down").exists()).toBe(false);
      expect(wrapper.find(".stat-tile__value--up").exists()).toBe(true);
    });
  });

  describe("kWh units", () => {
    it("shows a unit next to every kWh value rendered on the tiles", () => {
      const wrapper = mountCard();

      const units = wrapper.findAll(".stat-tile__unit").map((el) => el.text());
      expect(units.length).toBeGreaterThan(0);
      units.forEach((unit) => expect(unit).toBe("kWh"));

      // Last-period sub line and comparison sub line both carry raw kWh figures too.
      expect(wrapper.text()).toContain("kWh");
    });
  });
});

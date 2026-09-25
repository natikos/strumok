import { ArrowDown, ArrowUp } from "@primeicons/vue";
import Skeleton from "primevue/skeleton";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  DaysIntoPeriod,
  MomChange,
  PeriodUsage,
  SeasonComparison,
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

const seasonComparison: SeasonComparison = {
  season: "summer",
  currentKwh: 180,
  currentPeriodCount: 2,
  previousYearKwh: 150.4,
  previousPeriodCount: 2,
  deltaPercent: 19.7,
  direction: "up",
};

interface MountOverrides {
  lastPeriod?: PeriodUsage | null;
  momChange?: MomChange | null;
  daysIntoPeriod?: DaysIntoPeriod;
  seasonComparison?: SeasonComparison | null;
  missedPeriods?: number;
  isLoading?: boolean;
}

function mountCard(overrides: MountOverrides = {}) {
  return mountWithPlugins(StatTilesCard, {
    props: {
      lastPeriod,
      momChange,
      daysIntoPeriod,
      seasonComparison,
      ...overrides,
    },
    global: { components: { Skeleton } },
  });
}

describe("StatTilesCard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 6, 15)); // July — summer, matching `seasonComparison` fixture
  });

  afterEach(() => {
    vi.useRealTimers();
  });

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

      const comparisonTile = wrapper.findAll(".stat-tile")[1]!;
      expect(comparisonTile.text()).toContain("Missed periods");
      expect(comparisonTile.text()).toContain("2");
      expect(comparisonTile.text()).not.toContain("vs ");
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

    it("shows an empty season-comparison tile when seasonComparison is null", () => {
      const wrapper = mountCard({ seasonComparison: null });

      const tiles = wrapper.findAll(".stat-tile");
      expect(tiles[2]?.classes()).toContain("stat-tile--empty");
      expect(tiles[2]?.text()).toContain("—");
    });

    it("names the current season when seasonComparison is null", () => {
      const wrapper = mountCard({ seasonComparison: null });

      const tile = wrapper.findAll(".stat-tile")[2]!;
      expect(tile.text()).toContain("Summer");
      expect(tile.text()).not.toContain("Needs 2 periods");
    });
  });

  describe("season comparison tile", () => {
    it("shows the percent delta, direction icon, current season, and last year's value", () => {
      const wrapper = mountCard();

      const tile = wrapper.findAll(".stat-tile")[2]!;
      expect(tile.text()).toContain("19.7%");
      expect(tile.text()).toContain("Summer");
      expect(tile.text()).toContain("last year");
      expect(tile.text()).toContain("150.4");
      expect(tile.findComponent(ArrowUp).exists()).toBe(true);
      expect(tile.find(".stat-tile__value--up").exists()).toBe(true);
    });

    it("shows a down arrow and styling when this season's usage fell below last year's", () => {
      const wrapper = mountCard({
        seasonComparison: {
          season: "summer",
          currentKwh: 90,
          currentPeriodCount: 2,
          previousYearKwh: 120,
          previousPeriodCount: 2,
          deltaPercent: -25,
          direction: "down",
        },
      });

      const tile = wrapper.findAll(".stat-tile")[2]!;
      expect(tile.text()).toContain("25.0%");
      expect(tile.findComponent(ArrowDown).exists()).toBe(true);
      expect(tile.find(".stat-tile__value--down").exists()).toBe(true);
    });
  });

  describe("month-over-month direction", () => {
    it("shows a down arrow and the down styling class when usage decreased", () => {
      const wrapper = mountCard({
        momChange: { percent: -10, from: 100, to: 90, direction: "down", deltaUah: null },
      });

      const comparisonTile = wrapper.findAll(".stat-tile")[1]!;
      expect(comparisonTile.findComponent(ArrowDown).exists()).toBe(true);
      expect(comparisonTile.findComponent(ArrowUp).exists()).toBe(false);
      expect(comparisonTile.find(".stat-tile__value--down").exists()).toBe(true);
    });

    it("shows an up arrow and the up styling class when usage increased", () => {
      const wrapper = mountCard({
        momChange: { percent: 10, from: 100, to: 110, direction: "up", deltaUah: null },
      });

      const comparisonTile = wrapper.findAll(".stat-tile")[1]!;
      expect(comparisonTile.findComponent(ArrowUp).exists()).toBe(true);
      expect(comparisonTile.findComponent(ArrowDown).exists()).toBe(false);
      expect(comparisonTile.find(".stat-tile__value--up").exists()).toBe(true);
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

import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";

const { listMyMeterReadings, listMyStatements } = vi.hoisted(() => ({
  listMyMeterReadings: vi.fn(),
  listMyStatements: vi.fn(),
}));

vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

// vitest runs with isolate: false, so module mocks are scoped with doMock and
// a fresh import; a hoisted vi.mock would leak into other files' imports.
function mockApis(): void {
  vi.doMock("@shared/api/meter-readings", () => ({
    listMyMeterReadings,
    createMeterReading: vi.fn(),
  }));

  vi.doMock("@shared/api/billing", () => ({
    getBalance: vi.fn().mockResolvedValue(null),
    getPaymentDetails: vi.fn().mockResolvedValue(null),
    listMyStatements,
    listStatements: vi.fn().mockResolvedValue([]),
    listAdjustments: vi.fn().mockResolvedValue([]),
    getShortfall: vi.fn().mockResolvedValue(null),
    getBankCoverage: vi.fn().mockResolvedValue(null),
    getCurrentPeriod: vi.fn().mockResolvedValue({ period: "2026-09", status: "open" }),
  }));
}

const pastItem = {
  household_id: 9,
  household_name: "Plot Nine",
  is_current_owner: false,
  owned_since: "2025-01-01",
  owned_until: "2026-03-10",
  has_previous_owner: false,
  balance: {
    balance_uah: "80.00",
    household_id: 9,
    periods: [],
    total_due_uah: "80.00",
    total_paid_uah: "0.00",
    unpaid_months: 1,
  },
  statements: [],
};

const SUBMISSION_STUBS = {
  BalanceStrip: true,
  ShortfallNotice: true,
  BankCoverageNotice: true,
  SubmissionCard: { template: '<div data-testid="submission-card" />' },
  StatTilesCard: true,
  BillSummaryCard: true,
  FirstRunGuideCard: true,
  EmptyUsageCard: true,
  UsageChartCard: true,
  YearOverYearCard: true,
  DayNightSplitCard: true,
  SeasonCard: true,
  PastHouseholdNotice: true,
};

async function mountPage(options: { pastOnly: boolean }) {
  vi.resetModules();
  mockApis();
  const { useCurrentHousehold } = await import("@/features/households/useCurrentHousehold");
  useCurrentHousehold().setHouseholds(options.pastOnly ? [] : [{ id: 1, name: "Plot 1" }]);
  useCurrentHousehold().setPastOnly(options.pastOnly);
  const { default: DashboardPage } = await import("./DashboardPage.vue");
  const wrapper = mount(DashboardPage, {
    global: { plugins: appPlugins(), stubs: SUBMISSION_STUBS },
  });
  await flushPromises();
  return wrapper;
}

describe("DashboardPage for a former owner with no plot", () => {
  beforeEach(() => {
    listMyMeterReadings.mockReset().mockResolvedValue([]);
    listMyStatements.mockReset().mockResolvedValue([pastItem]);
  });

  afterEach(() => {
    vi.doUnmock("@shared/api/meter-readings");
    vi.doUnmock("@shared/api/billing");
  });

  it("shows the gave-up plots and no submission form, and loads no readings", async () => {
    const wrapper = await mountPage({ pastOnly: true });

    expect(wrapper.text()).toContain("Plot Nine");
    expect(wrapper.find('[data-testid="submission-card"]').exists()).toBe(false);
    expect(listMyMeterReadings).not.toHaveBeenCalled();
  });

  it("still shows the submission form for a user who holds a plot", async () => {
    const wrapper = await mountPage({ pastOnly: false });

    expect(wrapper.find('[data-testid="submission-card"]').exists()).toBe(true);
    expect(listMyMeterReadings).toHaveBeenCalled();
  });
});

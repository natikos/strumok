import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
import { appPlugins } from "@/shared/testing/mount";

import DashboardPage from "./DashboardPage.vue";

const { listMyMeterReadings, listMyStatements } = vi.hoisted(() => ({
  listMyMeterReadings: vi.fn(),
  listMyStatements: vi.fn(),
}));

vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("@shared/api/meter-readings", () => ({
  listMyMeterReadings,
  createMeterReading: vi.fn(),
}));

vi.mock("@shared/api/billing", () => ({
  getBalance: vi.fn().mockResolvedValue(null),
  getPaymentDetails: vi.fn().mockResolvedValue(null),
  listMyStatements,
  listStatements: vi.fn().mockResolvedValue([]),
  listAdjustments: vi.fn().mockResolvedValue([]),
  getShortfall: vi.fn().mockResolvedValue(null),
  getBankCoverage: vi.fn().mockResolvedValue(null),
}));

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

async function mountPage() {
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
    useCurrentHousehold().setHouseholds([]);
    useCurrentHousehold().setPastOnly(true);
  });

  afterEach(() => {
    useCurrentHousehold().setPastOnly(false);
  });

  it("shows the gave-up plots and no submission form, and loads no readings", async () => {
    const wrapper = await mountPage();

    expect(wrapper.text()).toContain("Plot Nine");
    expect(wrapper.find('[data-testid="submission-card"]').exists()).toBe(false);
    expect(listMyMeterReadings).not.toHaveBeenCalled();
  });

  it("still shows the submission form for a user who holds a plot", async () => {
    useCurrentHousehold().setPastOnly(false);
    useCurrentHousehold().setHouseholds([{ id: 1, name: "Plot 1" }]);
    const wrapper = await mountPage();

    expect(wrapper.find('[data-testid="submission-card"]').exists()).toBe(true);
    expect(listMyMeterReadings).toHaveBeenCalled();
  });
});

import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { AdminDashboardOut } from "@shared/api/admin";

import AdminPage from "./AdminPage.vue";

const { getAdminDashboard } = vi.hoisted(() => ({
  getAdminDashboard: vi.fn(),
}));

vi.mock("@shared/api/admin", () => ({
  getAdminDashboard,
}));

const stubs = {
  Tabs: { template: "<div><slot /></div>" },
  TabList: { template: "<div><slot /></div>" },
  Tab: { template: "<div><slot /></div>" },
  TabPanels: { template: "<div><slot /></div>" },
  TabPanel: { template: "<div><slot /></div>" },
  AdminHouseholdAssignment: true,
  ElectricityRatesSettings: true,
  ProgressSpinner: true,
};

function makeDashboard(): AdminDashboardOut {
  return {
    current_period: "2026-09",
    households: [
      {
        id: 10,
        name: "Plot 10",
        owner: {
          email: "owner@example.com",
          first_name: "Ada",
          id: 1,
          is_active: true,
          last_name: "Owner",
        },
        submission_status: "submitted",
        submitted_at: "2026-10-02T09:00:00.000Z",
        latest_period: "2026-08",
        latest_usage_kwh: "1234.5",
        latest_amount_charged_uah: "1234.50",
      },
      {
        id: 20,
        name: "Plot 20",
        owner: null,
        submission_status: "missing",
        submitted_at: null,
        latest_period: null,
        latest_usage_kwh: null,
        latest_amount_charged_uah: null,
      },
    ],
  };
}

describe("AdminPage submission overview", () => {
  beforeEach(() => {
    getAdminDashboard.mockReset();
    getAdminDashboard.mockResolvedValue(makeDashboard());
  });

  it("loads the dashboard and renders submitted, missing, and nullable latest values", async () => {
    const wrapper = mount(AdminPage, {
      global: {
        plugins: appPlugins(),
        stubs,
      },
    });
    await flushPromises();

    expect(getAdminDashboard).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("Current period: 2026-09");
    expect(wrapper.text()).toContain("Plot 10");
    expect(wrapper.text()).toContain("Ada Owner");
    expect(wrapper.text()).toContain("Submitted");
    expect(wrapper.text()).toContain("1,234.5 kWh");
    expect(wrapper.text()).toContain("1,234.50");
    expect(wrapper.text()).toContain("Plot 20");
    expect(wrapper.text()).toContain("Missing");
    expect(wrapper.text()).toContain("— kWh");
    expect(wrapper.text()).toContain("—");
    expect(wrapper.text()).toContain("—");
  });

  it("renders a retryable error if the dashboard request fails", async () => {
    getAdminDashboard.mockRejectedValueOnce(new Error("network down"));

    const wrapper = mount(AdminPage, {
      global: {
        plugins: appPlugins(),
        stubs,
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("Something went wrong. Please try again");
    expect(wrapper.find("button").exists()).toBe(true);
  });
});

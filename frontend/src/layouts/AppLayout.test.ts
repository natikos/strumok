import { flushPromises, mount } from "@vue/test-utils";
import { Button, Card } from "primevue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
import ErrorState from "@/shared/components/ErrorState.vue";
import { appPlugins } from "@/shared/testing/mount";
import Typography from "@/shared/Typography.vue";
import type { UserWithHouseholdsOut } from "@shared/api/auth";
import type * as VueRouter from "vue-router";

import AppLayout from "./AppLayout.vue";

const { getMe, logoutUser } = vi.hoisted(() => ({
  getMe: vi.fn(),
  logoutUser: vi.fn(),
}));

vi.mock("primevue/usetoast", () => ({ useToast: () => ({ add: vi.fn() }) }));

vi.mock("@shared/api/auth", () => ({
  getMe,
  logoutUser,
}));

vi.mock("vue-router", async (importOriginal) => {
  const actual = await importOriginal<typeof VueRouter>();
  return {
    ...actual,
    useRoute: () => ({ path: "/" }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  };
});

function makeMe(overrides: Partial<UserWithHouseholdsOut> = {}): UserWithHouseholdsOut {
  return {
    id: 1,
    email: "resident@example.com",
    first_name: "Olena",
    last_name: "Kovalenko",
    is_admin: false,
    has_past_households: false,
    is_active: true,
    email_verified: true,
    verification_email_retry_after_seconds: 0,
    theme: "light",
    language: "en",
    reminder_hour: 9,
    households: [],
    ...overrides,
  };
}

async function mountLayout() {
  const wrapper = mount(AppLayout, {
    global: {
      plugins: appPlugins(),
      components: {
        Button,
        Card,
        ErrorState,
        Typography,
      },
      stubs: {
        RouterView: true,
        Select: true,
        AuthLayout: {
          template: "<div><slot /></div>",
        },
      },
    },
  });

  await flushPromises();
  return wrapper;
}

describe("AppLayout household-membership gate", () => {
  beforeEach(() => {
    getMe.mockReset();
    logoutUser.mockReset();
    useCurrentHousehold().setHouseholds([]);
    useCurrentHousehold().setPastOnly(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("blocks behind NoHouseholdScreen and hides the sidebar/nav when the resident has no household", async () => {
    getMe.mockResolvedValue(makeMe({ households: [] }));

    const wrapper = await mountLayout();

    expect(wrapper.findComponent({ name: "NoHouseholdScreen" }).exists()).toBe(true);
    expect(wrapper.find(".app-sidebar").exists()).toBe(false);
    expect(wrapper.find(".app-mobile-nav").exists()).toBe(false);
  });

  it("renders the normal sidebar/nav layout when the resident already has a household", async () => {
    getMe.mockResolvedValue(makeMe({ households: [{ id: 7, name: "Plot 7" }] }));

    const wrapper = await mountLayout();

    expect(wrapper.findComponent({ name: "NoHouseholdScreen" }).exists()).toBe(false);
    expect(wrapper.find(".app-sidebar").exists()).toBe(true);
  });

  it("unblocks into the normal layout and adopts the fresh households when the child reports assignment", async () => {
    getMe.mockResolvedValue(makeMe({ households: [] }));

    const wrapper = await mountLayout();
    expect(wrapper.findComponent({ name: "NoHouseholdScreen" }).exists()).toBe(true);

    const updatedMe = makeMe({
      first_name: "Petro",
      households: [
        { id: 3, name: "Plot 3" },
        { id: 4, name: "Plot 4" },
      ],
    });

    await wrapper.findComponent({ name: "NoHouseholdScreen" }).vm.$emit("unblocked", updatedMe);
    await flushPromises();

    expect(wrapper.findComponent({ name: "NoHouseholdScreen" }).exists()).toBe(false);
    expect(wrapper.find(".app-sidebar").exists()).toBe(true);
    expect(useCurrentHousehold().households.value).toEqual([
      { id: 3, name: "Plot 3" },
      { id: 4, name: "Plot 4" },
    ]);
  });

  it("shows the app read-only, not the blocking screen, for a former owner with no plot", async () => {
    getMe.mockResolvedValue(makeMe({ households: [], has_past_households: true }));

    const wrapper = await mountLayout();

    expect(wrapper.findComponent({ name: "NoHouseholdScreen" }).exists()).toBe(false);
    expect(wrapper.find(".app-sidebar").exists()).toBe(true);
    expect(useCurrentHousehold().isPastOnly.value).toBe(true);
  });

  it("is not past-only when the user has no plot and never had one", async () => {
    getMe.mockResolvedValue(makeMe({ households: [], has_past_households: false }));

    await mountLayout();

    expect(useCurrentHousehold().isPastOnly.value).toBe(false);
  });

  it("is not past-only when the user still holds a plot even with past households", async () => {
    getMe.mockResolvedValue(
      makeMe({ households: [{ id: 7, name: "Plot 7" }], has_past_households: true })
    );

    await mountLayout();

    expect(useCurrentHousehold().isPastOnly.value).toBe(false);
  });

  it("clears past-only state when a former owner is later given a plot via check-again", async () => {
    useCurrentHousehold().setPastOnly(true);
    getMe.mockResolvedValue(makeMe({ households: [], has_past_households: false }));
    const wrapper = await mountLayout();
    expect(useCurrentHousehold().isPastOnly.value).toBe(false);

    await wrapper
      .findComponent({ name: "NoHouseholdScreen" })
      .vm.$emit("unblocked", makeMe({ households: [{ id: 2, name: "Plot 2" }] }));
    await flushPromises();

    expect(useCurrentHousehold().isPastOnly.value).toBe(false);
  });
});

describe("AppLayout unreachable session", () => {
  beforeEach(() => {
    getMe.mockReset();
    useCurrentHousehold().setHouseholds([]);
    useCurrentHousehold().setPastOnly(false);
  });

  it("shows a retry screen when /auth/me fails on the network, then loads on retry", async () => {
    getMe.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    getMe.mockResolvedValueOnce(makeMe({ households: [{ id: 7, name: "Plot 7" }] }));

    const wrapper = await mountLayout();

    expect(wrapper.find(".app-offline").exists()).toBe(true);
    expect(wrapper.find(".app-layout").exists()).toBe(false);

    await wrapper.find(".error-state__retry").trigger("click");
    await flushPromises();

    expect(wrapper.find(".app-offline").exists()).toBe(false);
    expect(wrapper.find(".app-layout").exists()).toBe(true);
  });
});

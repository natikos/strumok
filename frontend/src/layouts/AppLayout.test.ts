import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
import { appPlugins } from "@/shared/testing/mount";
import Typography from "@/shared/Typography.vue";
import type { UserWithHouseholdsOut } from "@shared/api/auth";
import type * as VueRouter from "vue-router";

import { Button, Card } from "primevue";
import AppLayout from "./AppLayout.vue";

const { getMe, logoutUser } = vi.hoisted(() => ({
  getMe: vi.fn(),
  logoutUser: vi.fn(),
}));

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
    is_active: true,
    email_verified: true,
    verification_email_retry_after_seconds: 0,
    theme: "light",
    language: "en",
    households: [],
    ...overrides,
  };
}

async function mountLayout() {
  const wrapper = mount(AppLayout, {
    global: {
      plugins: appPlugins(),
      components: { Typography, Button, Card },
      stubs: {
        RouterView: true,
        Select: true,
        AuthLayout: true,
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
});

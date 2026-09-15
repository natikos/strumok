import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import Card from "primevue/card";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import Typography from "@/shared/Typography.vue";
import type { UserWithHouseholdsOut } from "@shared/api/auth";
import type * as VueRouter from "vue-router";

import NoHouseholdScreen from "./NoHouseholdScreen.vue";

const { getMe, logoutUser } = vi.hoisted(() => ({
  getMe: vi.fn(),
  logoutUser: vi.fn(),
}));

vi.mock("@shared/api/auth", () => ({
  getMe,
  logoutUser,
}));

const replace = vi.fn();

vi.mock("vue-router", async (importOriginal) => {
  const actual = await importOriginal<typeof VueRouter>();
  return {
    ...actual,
    useRouter: () => ({ replace }),
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

function mountScreen() {
  return mount(NoHouseholdScreen, {
    global: {
      plugins: appPlugins(),
      components: { Button, Card, Typography },
      stubs: {
        // Real AuthLayout pulls in language/theme toggle components that are
        // irrelevant here; render its default slot only.
        AuthLayout: { template: "<div><slot /></div>" },
      },
    },
  });
}

function findButton(wrapper: ReturnType<typeof mountScreen>, label: string) {
  return wrapper.findAll("button").find((btn) => btn.text().includes(label));
}

describe("NoHouseholdScreen", () => {
  beforeEach(() => {
    getMe.mockReset();
    logoutUser.mockReset();
    replace.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits unblocked with the fresh user once a household has been assigned", async () => {
    const updatedMe = makeMe({ households: [{ id: 5, name: "Plot 5" }] });
    getMe.mockResolvedValue(updatedMe);

    const wrapper = mountScreen();
    const checkAgain = findButton(wrapper, "Check again");
    await checkAgain?.trigger("click");
    await flushPromises();

    expect(wrapper.emitted("unblocked")).toEqual([[updatedMe]]);
    expect(wrapper.find(".no-household-card__notice").exists()).toBe(false);
  });

  it("shows the still-not-assigned notice and does not emit when the resident remains unassigned", async () => {
    getMe.mockResolvedValue(makeMe({ households: [] }));

    const wrapper = mountScreen();
    const checkAgain = findButton(wrapper, "Check again");
    await checkAgain?.trigger("click");
    await flushPromises();

    expect(wrapper.emitted("unblocked")).toBeUndefined();
    expect(wrapper.find(".no-household-card__notice").exists()).toBe(true);
  });

  it("disables the check-again button while the request is in flight", async () => {
    let resolveGetMe!: (value: UserWithHouseholdsOut) => void;
    getMe.mockReturnValue(
      new Promise((resolve) => {
        resolveGetMe = resolve;
      })
    );

    const wrapper = mountScreen();
    const checkAgain = findButton(wrapper, "Check again");
    const clickPromise = checkAgain?.trigger("click");
    await flushPromises();

    expect(findButton(wrapper, "Check again")?.attributes("disabled")).toBeDefined();

    resolveGetMe(makeMe({ households: [] }));
    await clickPromise;
    await flushPromises();

    expect(findButton(wrapper, "Check again")?.attributes("disabled")).toBeUndefined();
  });

  it("logs out and navigates to the auth route when the resident gives up", async () => {
    logoutUser.mockResolvedValue(undefined);

    const wrapper = mountScreen();
    const logout = findButton(wrapper, "Logout");
    await logout?.trigger("click");
    await flushPromises();

    expect(logoutUser).toHaveBeenCalledOnce();
    expect(replace).toHaveBeenCalledWith("/auth");
  });

  it("disables the log-out button while logging out is in flight", async () => {
    let resolveLogout!: () => void;
    logoutUser.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveLogout = resolve;
      })
    );

    const wrapper = mountScreen();
    const logout = findButton(wrapper, "Logout");
    const clickPromise = logout?.trigger("click");
    await flushPromises();

    expect(findButton(wrapper, "Logout")?.attributes("disabled")).toBeDefined();

    resolveLogout();
    await clickPromise;
    await flushPromises();
  });
});

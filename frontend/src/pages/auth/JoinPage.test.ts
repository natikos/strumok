import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins, tUa } from "@/shared/testing/mount";
import type * as AuthApi from "@shared/api/auth";

import JoinPage from "./JoinPage.vue";

const { getJoinableHouseholds, push } = vi.hoisted(() => ({
  getJoinableHouseholds: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@shared/api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof AuthApi>();
  return { ...actual, getJoinableHouseholds, joinAsResident: vi.fn() };
});
vi.mock("vue-router", () => ({
  RouterLink: { template: "<a><slot /></a>" },
  useRouter: () => ({ push }),
}));
vi.mock("primevue/usetoast", () => ({ useToast: () => ({ add: vi.fn() }) }));

function mountPage() {
  return mount(JoinPage, {
    global: {
      plugins: appPlugins(),
      stubs: { AuthLayout: { template: "<div><slot /></div>" } },
    },
  });
}

describe("JoinPage", () => {
  beforeEach(() => {
    // PrimeVue's Select binds a matchMedia listener; jsdom doesn't implement it.
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        addEventListener: vi.fn(),
        matches: false,
        removeEventListener: vi.fn(),
      })
    );
    getJoinableHouseholds.mockReset();
    push.mockReset();
  });

  it("shows the sign-up form when free plots exist", async () => {
    getJoinableHouseholds.mockResolvedValue([{ id: 1, name: "Ділянка 1" }]);
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.find("form").exists()).toBe(true);
    expect(wrapper.text()).toContain(tUa("auth.joinPlot"));
  });

  it("tells the resident to contact the admin when no plot is free", async () => {
    getJoinableHouseholds.mockResolvedValue([]);
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.text()).toContain(tUa("auth.joinNoPlots"));
  });

  it("offers a retry when the plot list fails to load", async () => {
    getJoinableHouseholds.mockRejectedValue(new Error("offline"));
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.text()).toContain(tUa("auth.joinLoadFailed"));
  });
});

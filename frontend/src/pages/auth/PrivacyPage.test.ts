import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";

import PrivacyPage from "./PrivacyPage.vue";

vi.mock("@shared/api/auth-session", () => ({
  getAuthSessionState: () => ({ isAuthenticated: false, isEmailVerified: false }),
}));

describe("PrivacyPage", () => {
  it("renders every section and links back to login when signed out", () => {
    const wrapper = mount(PrivacyPage, {
      global: {
        plugins: appPlugins(),
        stubs: {
          AuthLayout: { template: "<div><slot /></div>" },
          RouterLink: { props: ["to"], template: '<a :href="to"><slot /></a>' },
        },
      },
    });

    expect(wrapper.findAll("section")).toHaveLength(5);
    expect(wrapper.find("a").attributes("href")).toBe("/auth");
  });
});

import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import Card from "primevue/card";
import ProgressSpinner from "primevue/progressspinner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import Typography from "@/shared/Typography.vue";
import type * as AuthApi from "@shared/api/auth";
import type * as VueRouter from "vue-router";

import VerifyEmailPage from "./VerifyEmailPage.vue";

const { confirmEmailVerification, getMe, logoutUser, sendVerificationEmailLink } = vi.hoisted(
  () => ({
    confirmEmailVerification: vi.fn(),
    getMe: vi.fn(),
    logoutUser: vi.fn(),
    sendVerificationEmailLink: vi.fn(),
  })
);

vi.mock("@shared/api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof AuthApi>();
  return {
    ...actual,
    confirmEmailVerification,
    getMe,
    logoutUser,
    sendVerificationEmailLink,
  };
});

const replace = vi.fn();

vi.mock("vue-router", async (importOriginal) => {
  const actual = await importOriginal<typeof VueRouter>();
  return {
    ...actual,
    useRoute: () => ({ query: { token: "expired-or-invalid-token" } }),
    useRouter: () => ({ replace }),
  };
});

function mountPage() {
  return mount(VerifyEmailPage, {
    global: {
      plugins: appPlugins(),
      components: { Button, Card, ProgressSpinner, Typography },
      stubs: {
        AuthLayout: { template: "<div><slot /></div>" },
      },
    },
  });
}

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    confirmEmailVerification.mockReset();
    getMe.mockReset();
    logoutUser.mockReset();
    sendVerificationEmailLink.mockReset();
    replace.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the error state without an unhandled rejection when a signed-out visitor's token sync also fails", async () => {
    // Regression for #64: a signed-out visitor following an expired/invalid
    // verification link has no session, so the nested syncUserState() call
    // (which fetches /auth/me) 401s too. That second failure must be caught,
    // not surfaced as an unhandled promise rejection.
    confirmEmailVerification.mockRejectedValue(new Error("invalidOrExpiredToken"));
    getMe.mockRejectedValue(new Error("unauthenticated"));

    const unhandledRejections: unknown[] = [];
    const onUnhandledRejection = (event: PromiseRejectionEvent): void => {
      unhandledRejections.push(event.reason);
    };
    window.addEventListener("unhandledrejection", onUnhandledRejection);

    const wrapper = mountPage();
    await flushPromises();

    // Give any unhandled rejection a microtask to surface before asserting.
    await new Promise((resolve) => setTimeout(resolve, 0));
    window.removeEventListener("unhandledrejection", onUnhandledRejection);

    expect(unhandledRejections).toEqual([]);
    expect(getMe).toHaveBeenCalledOnce();
    expect(wrapper.text()).toContain("expired");
    expect(replace).not.toHaveBeenCalled();
  });
});

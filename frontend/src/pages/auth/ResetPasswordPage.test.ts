import { Form, FormField } from "@primevue/forms";
import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import Card from "primevue/card";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Password from "primevue/password";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import Typography from "@/shared/Typography.vue";
import type * as AuthApi from "@shared/api/auth";
import FormFieldControl from "@shared/FormFieldControl.vue";

import ResetPasswordPage from "./ResetPasswordPage.vue";

const { confirmPasswordReset, query, replace } = vi.hoisted(() => ({
  confirmPasswordReset: vi.fn(),
  query: { token: "abc" } as Record<string, string>,
  replace: vi.fn(),
}));

vi.mock("@shared/api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof AuthApi>();
  return { ...actual, confirmPasswordReset };
});
vi.mock("vue-router", () => ({
  useRoute: () => ({ query }),
  useRouter: () => ({ replace }),
}));
vi.mock("primevue/usetoast", () => ({ useToast: () => ({ add: vi.fn() }) }));

function mountPage() {
  return mount(ResetPasswordPage, {
    global: {
      plugins: appPlugins(),
      stubs: { AuthLayout: { template: "<div><slot /></div>" } },
      components: {
        Button,
        Card,
        Form,
        FormField,
        FormFieldControl,
        InputText,
        Message,
        Password,
        Typography,
      },
    },
  });
}

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    confirmPasswordReset.mockReset();
    replace.mockReset();
    query["token"] = "abc";
  });

  it("shows the expired state with a request-new-link button when the token is missing", () => {
    delete query["token"];
    const wrapper = mountPage();

    expect(wrapper.text()).toContain("invalid or has expired");
    expect(wrapper.text()).toContain("Request a new link");
  });

  it("switches to the expired state when the API rejects the token", async () => {
    const { ApiError } = await import("@shared/api/auth");
    confirmPasswordReset.mockRejectedValue(new ApiError("invalidOrExpiredToken", 400));
    const wrapper = mountPage();

    for (const [i, input] of wrapper.findAll<HTMLInputElement>("input").entries()) {
      input.element.value = "brand-new-pass";
      await input.trigger("input");
      expect(i).toBeLessThan(2);
    }
    await flushPromises();
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(confirmPasswordReset).toHaveBeenCalledWith("abc", "brand-new-pass");
    expect(wrapper.text()).toContain("Request a new link");
  });
});

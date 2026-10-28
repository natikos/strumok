import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Password from "primevue/password";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type * as AuthApi from "@shared/api/auth";

import AccountSettings from "./AccountSettings.vue";

const { changePassword, requestEmailChange } = vi.hoisted(() => ({
  changePassword: vi.fn(),
  requestEmailChange: vi.fn(),
}));

vi.mock("@shared/api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof AuthApi>();
  return { ...actual, changePassword, requestEmailChange };
});

function mountSettings() {
  return mount(AccountSettings, {
    props: { currentEmail: "resident@example.com" },
    global: {
      plugins: appPlugins(),
      components: { Button, InputText, Message, Password },
    },
  });
}

async function fill(wrapper: ReturnType<typeof mountSettings>, index: number, value: string) {
  const input = wrapper.findAll<HTMLInputElement>("input")[index]!;
  input.element.value = value;
  await input.trigger("input");
}

describe("AccountSettings", () => {
  beforeEach(() => {
    changePassword.mockReset();
    requestEmailChange.mockReset();
  });

  it("changes the password and confirms it", async () => {
    changePassword.mockResolvedValue(undefined);
    const wrapper = mountSettings();

    await wrapper.findAll("button")[0]!.trigger("click");
    await fill(wrapper, 0, "old-password");
    await fill(wrapper, 1, "brand-new-pass");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(changePassword).toHaveBeenCalledWith({
      current_password: "old-password",
      new_password: "brand-new-pass",
    });
    expect(wrapper.text()).toContain("Password changed");
    expect(wrapper.find("form").exists()).toBe(false);
  });

  it("shows the throttle countdown on a 429 and keeps the form open", async () => {
    const { ApiError } = await import("@shared/api/auth");
    requestEmailChange.mockRejectedValue(new ApiError("tooManyAttempts", 429, 90));
    const wrapper = mountSettings();

    await wrapper.findAll("button")[1]!.trigger("click");
    await fill(wrapper, 0, "new@example.com");
    await fill(wrapper, 1, "old-password");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("01:30");
    expect(wrapper.find("form").exists()).toBe(true);
  });
});

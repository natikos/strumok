import { Form, FormField } from "@primevue/forms";
import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import Card from "primevue/card";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Password from "primevue/password";
import SelectButton from "primevue/selectbutton";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import Typography from "@/shared/Typography.vue";
import type * as AuthApi from "@shared/api/auth";
import FormFieldControl from "@shared/FormFieldControl.vue";

import AuthForm from "./AuthForm.vue";

const { loginUser } = vi.hoisted(() => ({ loginUser: vi.fn() }));

vi.mock("@shared/api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof AuthApi>();
  return { ...actual, loginUser };
});

vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function mountForm() {
  return mount(AuthForm, {
    global: {
      plugins: appPlugins(),
      components: { Button, Card, Form, FormField, FormFieldControl, InputText, Message, Password, SelectButton, Typography },
    },
  });
}

async function submitLogin(wrapper: ReturnType<typeof mountForm>) {
  for (const [id, value] of [
    ["#auth-email", "resident@example.com"],
    ["input[name=password]", "wrong-password"],
  ] as const) {
    const input = wrapper.find<HTMLInputElement>(id);
    input.element.value = value;
    await input.trigger("input");
  }
  await flushPromises();
  await wrapper.find("form").trigger("submit");
  await flushPromises();
}

describe("AuthForm login throttling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    loginUser.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it("shows a countdown and disables submit after a 429, then re-enables", async () => {
    const { ApiError } = await import("@shared/api/auth");
    loginUser.mockRejectedValue(new ApiError("tooManyAttempts", 429, 90));
    const wrapper = mountForm();

    await submitLogin(wrapper);

    expect(wrapper.text()).toContain("01:30");
    expect(wrapper.find("button[type=submit]").attributes("disabled")).toBeDefined();

    await vi.advanceTimersByTimeAsync(90_000);

    expect(wrapper.text()).not.toContain("Too many failed attempts");
    expect(wrapper.find("button[type=submit]").attributes("disabled")).toBeUndefined();
  });
});

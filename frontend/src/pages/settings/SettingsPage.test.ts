import { mount } from "@vue/test-utils";
import ToggleSwitch from "primevue/toggleswitch";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

import { appPlugins } from "@/shared/testing/mount";
import type { PushToggleState } from "@features/push-notifications/usePushNotifications";

import SettingsPage from "./SettingsPage.vue";

/**
 * `usePushNotifications` itself is exercised in its own test (state
 * derivation from browser globals); here we mock it so each state can be fed
 * to the page directly and we assert only on the page's own responsibility --
 * the hint text and switch-enabled/disabled mapping.
 */
const { usePushNotifications } = vi.hoisted(() => ({
  usePushNotifications: vi.fn(),
}));

vi.mock("@features/push-notifications/usePushNotifications", () => ({
  usePushNotifications,
}));

vi.mock("primevue/usetoast", () => ({
  useToast: () => ({ add: vi.fn() }),
}));

function mockPushState(initial: PushToggleState) {
  const state = ref(initial);
  const enable = vi.fn().mockResolvedValue(undefined);
  const disable = vi.fn().mockResolvedValue(undefined);
  usePushNotifications.mockReturnValue({ state, enable, disable });
  return { state, enable, disable };
}

function mountSettingsPage() {
  return mount(SettingsPage, {
    global: {
      plugins: appPlugins(),
      components: { ToggleSwitch },
      stubs: { ThemeToggleButton: true, LanguageToggleButton: true },
    },
  });
}

describe("SettingsPage notifications section", () => {
  beforeEach(() => {
    usePushNotifications.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it.each([
    ["off", "Notifications will arrive on the 1st and 5th of each month"],
    ["on", "Enabled · reminders on the 1st and 5th"],
    ["requesting", "Requesting permission…"],
    [
      "denied",
      "Blocked in browser settings — enable notifications for the app and reload the page",
    ],
    [
      "ios-not-installed",
      "On iPhone, first add the app to the home screen (Share → Add to Home Screen), then enable this",
    ],
    ["unsupported", "Unavailable in this browser"],
  ] as [PushToggleState, string][])(
    "shows the %s hint for push state %s",
    (state, expectedHint) => {
      mockPushState(state);

      const wrapper = mountSettingsPage();

      expect(wrapper.text()).toContain(expectedHint);
    }
  );

  it("does not render a switch at all when push is unsupported", () => {
    mockPushState("unsupported");

    const wrapper = mountSettingsPage();

    expect(wrapper.find('input[role="switch"]').exists()).toBe(false);
  });

  it.each(["off", "on", "ios-not-installed"] as PushToggleState[])(
    "leaves the switch enabled in the %s state",
    (state) => {
      mockPushState(state);

      const wrapper = mountSettingsPage();

      expect(wrapper.find('input[role="switch"]').attributes("disabled")).toBeUndefined();
    }
  );

  it.each(["denied", "requesting"] as PushToggleState[])(
    "disables the switch in the %s state so the resident can't act on a state that ignores input",
    (state) => {
      mockPushState(state);

      const wrapper = mountSettingsPage();

      expect(wrapper.find('input[role="switch"]').attributes("disabled")).toBeDefined();
    }
  );

  it("reflects on/off as the switch's checked state", () => {
    mockPushState("on");
    const onWrapper = mountSettingsPage();
    expect(onWrapper.find<HTMLInputElement>('input[role="switch"]').element.checked).toBe(true);

    mockPushState("off");
    const offWrapper = mountSettingsPage();
    expect(offWrapper.find<HTMLInputElement>('input[role="switch"]').element.checked).toBe(false);
  });

  it("calls enable() when the resident turns the switch on", () => {
    const { enable, disable } = mockPushState("off");
    const wrapper = mountSettingsPage();

    wrapper.findComponent(ToggleSwitch).vm.$emit("update:modelValue", true);

    expect(enable).toHaveBeenCalledOnce();
    expect(disable).not.toHaveBeenCalled();
  });

  it("calls disable() when the resident turns the switch off", () => {
    const { enable, disable } = mockPushState("on");
    const wrapper = mountSettingsPage();

    wrapper.findComponent(ToggleSwitch).vm.$emit("update:modelValue", false);

    expect(disable).toHaveBeenCalledOnce();
    expect(enable).not.toHaveBeenCalled();
  });

  it("ignores a toggle attempt while the iOS PWA is not yet installed", () => {
    // The switch isn't disabled in this state (it doubles as the entry point
    // for the "add to home screen" instructions), but acting on it must not
    // call enable()/disable() -- there is nothing installed to subscribe.
    const { enable, disable } = mockPushState("ios-not-installed");
    const wrapper = mountSettingsPage();

    wrapper.findComponent(ToggleSwitch).vm.$emit("update:modelValue", true);

    expect(enable).not.toHaveBeenCalled();
    expect(disable).not.toHaveBeenCalled();
  });
});

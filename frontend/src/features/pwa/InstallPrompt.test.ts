import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

// The suite runs with isolate: false and the prompt state is module-level, so
// load a fresh copy of both for every test.
let InstallPrompt: Component;
let captureInstallPrompt: () => void;

async function load(): Promise<void> {
  vi.resetModules();
  ({ captureInstallPrompt } = await import("./useInstallPrompt"));
  InstallPrompt = (await import("./InstallPrompt.vue")).default;
  captureInstallPrompt();
}

function mountPrompt() {
  return mount(InstallPrompt, { global: { plugins: appPlugins() } });
}

function fireInstallEvent(outcome: "accepted" | "dismissed" = "accepted") {
  const event = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome }),
  });
  window.dispatchEvent(event);
  return event;
}

describe("InstallPrompt", () => {
  beforeAll(() => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query }));
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(async () => {
    localStorage.clear();
    await load();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is hidden until the browser offers installation", async () => {
    const wrapper = mountPrompt();
    expect(wrapper.find(".install").exists()).toBe(false);

    fireInstallEvent();
    await flushPromises();

    expect(wrapper.find(".install").exists()).toBe(true);
  });

  it("opens the browser's install dialog from the button", async () => {
    const wrapper = mountPrompt();
    const event = fireInstallEvent();
    await flushPromises();

    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(event.prompt).toHaveBeenCalledOnce();
    expect(wrapper.find(".install").exists()).toBe(false);
  });

  it("remembers a dismissal on this device", async () => {
    const wrapper = mountPrompt();
    fireInstallEvent();
    await flushPromises();

    await wrapper.findAll("button")[1]!.trigger("click");
    expect(wrapper.find(".install").exists()).toBe(false);
    expect(localStorage.getItem("strumok:install-prompt-dismissed")).not.toBeNull();

    await load();
    const again = mountPrompt();
    fireInstallEvent();
    await flushPromises();
    expect(again.find(".install").exists()).toBe(false);
  });

  it("shows the Add to Home Screen steps on iPhone, without an install button", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
    );

    const wrapper = mountPrompt();

    expect(wrapper.text()).toContain("Add to Home Screen");
    expect(wrapper.findAll("button")).toHaveLength(1);
  });
});

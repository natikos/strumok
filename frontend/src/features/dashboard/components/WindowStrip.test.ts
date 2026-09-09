import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mountWithPlugins } from "@/shared/testing/mount";

import WindowStrip from "./WindowStrip.vue";

describe("WindowStrip", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("always renders exactly 5 segments and 5 captions, one per deadline day", () => {
    vi.setSystemTime(new Date(2026, 5, 3));
    const wrapper = mountWithPlugins(WindowStrip);

    expect(wrapper.findAll(".window-strip__segment")).toHaveLength(5);
    const captions = wrapper.findAll(".window-strip__caption").map((el) => el.text());
    expect(captions).toEqual(["1", "2", "3", "4", "5"]);
  });

  it("marks days before today as elapsed, today as today, and later days as future", () => {
    vi.setSystemTime(new Date(2026, 5, 3));
    const wrapper = mountWithPlugins(WindowStrip);

    const segments = wrapper.findAll(".window-strip__segment");
    expect(segments[0]?.classes()).toContain("window-strip__segment--elapsed");
    expect(segments[1]?.classes()).toContain("window-strip__segment--elapsed");
    expect(segments[2]?.classes()).toContain("window-strip__segment--today");
    expect(segments[3]?.classes()).toContain("window-strip__segment--future");
    expect(segments[4]?.classes()).toContain("window-strip__segment--future");

    const todayCaption = wrapper.find(".window-strip__caption--today");
    expect(todayCaption.exists()).toBe(true);
    expect(todayCaption.text()).toBe("3");
  });

  it("on day 1, only the first segment is today and none are elapsed", () => {
    vi.setSystemTime(new Date(2026, 5, 1));
    const wrapper = mountWithPlugins(WindowStrip);

    const segments = wrapper.findAll(".window-strip__segment");
    expect(segments[0]?.classes()).toContain("window-strip__segment--today");
    segments.slice(1).forEach((segment) => {
      expect(segment.classes()).toContain("window-strip__segment--future");
    });
  });

  it("when overdue, every segment reads as elapsed and none is marked today", () => {
    vi.setSystemTime(new Date(2026, 5, 3));
    const wrapper = mountWithPlugins(WindowStrip, { props: { isOverdue: true } });

    const segments = wrapper.findAll(".window-strip__segment");
    segments.forEach((segment) => {
      expect(segment.classes()).toContain("window-strip__segment--elapsed");
    });
    expect(wrapper.find(".window-strip__caption--today").exists()).toBe(false);
    expect(wrapper.classes()).toContain("window-strip--overdue");
  });

  it("exposes the strip as an image role with a non-empty aria-label describing progress", () => {
    vi.setSystemTime(new Date(2026, 5, 3));
    const wrapper = mountWithPlugins(WindowStrip);

    const img = wrapper.find('[role="img"]');
    expect(img.exists()).toBe(true);
    expect(img.attributes("aria-label")).toBeTruthy();
    expect(img.attributes("aria-label")).toContain("2 of 5");
  });
});

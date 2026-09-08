import Button from "primevue/button";
import Skeleton from "primevue/skeleton";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mountWithPlugins } from "@/shared/testing/mount";

import DeadlineStatusCard from "./DeadlineStatusCard.vue";

function mountCard(props: Partial<InstanceType<typeof DeadlineStatusCard>["$props"]> = {}) {
  return mountWithPlugins(DeadlineStatusCard, {
    props: {
      status: "due",
      daysLeft: 3,
      billingMonthIndex: 5,
      ...props,
    },
    global: {
      components: { Skeleton, Button },
    },
  });
}

describe("DeadlineStatusCard", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("renders the days-left headline with correct plural for 1 day", () => {
    vi.setSystemTime(new Date(2026, 5, 4));
    const wrapper = mountCard({ status: "due", daysLeft: 1 });

    expect(wrapper.find(".deadline-status__headline").text()).toContain("1 day left");
  });

  it("renders the days-left headline with correct plural for 3 days", () => {
    vi.setSystemTime(new Date(2026, 5, 2));
    const wrapper = mountCard({ status: "due", daysLeft: 3 });

    expect(wrapper.find(".deadline-status__headline").text()).toContain("3 days left");
  });

  it("renders the days-left headline with correct plural for 5 days", () => {
    vi.setSystemTime(new Date(2026, 5, 1));
    const wrapper = mountCard({ status: "due", daysLeft: 5 });

    expect(wrapper.find(".deadline-status__headline").text()).toContain("5 days left");
  });

  it("renders the due status with its pill text and accent class", () => {
    vi.setSystemTime(new Date(2026, 5, 2));
    const wrapper = mountCard({ status: "due" });

    expect(wrapper.classes()).toContain("deadline-status--due");
    expect(wrapper.text()).toContain("Due");
  });

  it("renders the overdue status with its pill text and accent class", () => {
    vi.setSystemTime(new Date(2026, 5, 20));
    const wrapper = mountCard({ status: "overdue", daysLeft: 0 });

    expect(wrapper.classes()).toContain("deadline-status--overdue");
    expect(wrapper.text()).toContain("Overdue");
    expect(wrapper.find(".deadline-status__headline").text()).toContain(
      "Submission deadline passed"
    );
  });

  it("renders the submitted status with its pill text and accent class", () => {
    vi.setSystemTime(new Date(2026, 5, 20));
    const wrapper = mountCard({
      status: "submitted",
      submittedAt: new Date(2026, 5, 3, 9, 0).toISOString(),
      dayMeterValue: 120,
      nightMeterValue: 60,
    });

    expect(wrapper.classes()).toContain("deadline-status--submitted");
    expect(wrapper.text()).toContain("Submitted");
    expect(wrapper.find(".deadline-status__headline").text()).toContain("Reading submitted");
  });

  it("renders the submitted-late status with its pill text and accent class", () => {
    vi.setSystemTime(new Date(2026, 5, 20));
    const wrapper = mountCard({
      status: "submitted-late",
      submittedAt: new Date(2026, 5, 10, 9, 0).toISOString(),
      dayMeterValue: 120,
      nightMeterValue: 60,
    });

    expect(wrapper.classes()).toContain("deadline-status--submitted-late");
    expect(wrapper.text()).toContain("Submitted late");
    expect(wrapper.find(".deadline-status__subline").text()).toContain("Submitted late");
  });

  it("renders first-period copy instead of the countdown when isFirstPeriod is true", () => {
    vi.setSystemTime(new Date(2026, 5, 2));
    const wrapper = mountCard({ status: "due", isFirstPeriod: true });

    expect(wrapper.find(".deadline-status__headline").text()).toContain("First reading");
    expect(wrapper.find(".deadline-status__headline").text()).not.toContain("left");
  });

  it("renders both meter values, formatted, when submitted", () => {
    vi.setSystemTime(new Date(2026, 5, 20));
    const wrapper = mountCard({
      status: "submitted",
      submittedAt: new Date(2026, 5, 3, 9, 0).toISOString(),
      dayMeterValue: 1234,
      nightMeterValue: 56,
    });

    expect(wrapper.find(".deadline-status__values").exists()).toBe(true);
    expect(wrapper.text()).toContain("1,234");
    expect(wrapper.text()).toContain("56");
  });

  it("renders an outlined edit button that emits edit when submitted", async () => {
    vi.setSystemTime(new Date(2026, 5, 20));
    const wrapper = mountCard({
      status: "submitted",
      submittedAt: new Date(2026, 5, 3, 9, 0).toISOString(),
      dayMeterValue: 120,
      nightMeterValue: 60,
    });

    const editButton = wrapper.findComponent(Button);
    expect(editButton.exists()).toBe(true);
    expect(editButton.props("label")).toBe("Edit reading");
    expect(editButton.props("outlined")).toBe(true);

    await editButton.trigger("click");
    expect(wrapper.emitted("edit")).toHaveLength(1);
  });

  it("renders the edit button in the submitted-late state too", () => {
    vi.setSystemTime(new Date(2026, 5, 20));
    const wrapper = mountCard({
      status: "submitted-late",
      submittedAt: new Date(2026, 5, 10, 9, 0).toISOString(),
      dayMeterValue: 120,
      nightMeterValue: 60,
    });

    expect(wrapper.findComponent(Button).exists()).toBe(true);
  });

  it("renders no edit button while the window is still open", () => {
    vi.setSystemTime(new Date(2026, 5, 2));
    const wrapper = mountCard({ status: "due" });

    expect(wrapper.findComponent(Button).exists()).toBe(false);
    expect(wrapper.find(".deadline-status__footer").exists()).toBe(false);
  });

  it("renders exactly 5 window segments and marks the current day", () => {
    vi.setSystemTime(new Date(2026, 5, 3));
    const wrapper = mountCard({ status: "due", daysLeft: 3 });

    const segments = wrapper.findAll(".deadline-status__strip-segment");
    expect(segments).toHaveLength(5);

    const todayCaption = wrapper.find(".deadline-status__strip-caption--today");
    expect(todayCaption.exists()).toBe(true);
    expect(todayCaption.text()).toBe("3");
  });

  it("renders skeletons and no headline while loading", () => {
    const wrapper = mountCard({ isLoading: true });

    expect(wrapper.findAllComponents(Skeleton).length).toBeGreaterThan(0);
    expect(wrapper.find(".deadline-status__headline").exists()).toBe(false);
  });

  it("has an aria-live region and an aria-label on the window strip", () => {
    vi.setSystemTime(new Date(2026, 5, 2));
    const wrapper = mountCard({ status: "due" });

    expect(wrapper.find('[role="status"][aria-live="polite"]').exists()).toBe(true);
    expect(wrapper.find('[role="img"]').attributes("aria-label")).toBeTruthy();
  });
});

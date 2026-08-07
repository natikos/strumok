import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import Skeleton from "primevue/skeleton";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mountWithPlugins } from "@/shared/testing/mount";
import type { MeterReadingOut } from "@shared/api/meter-readings";

import MeterSubmitCard from "./MeterSubmitCard.vue";

function makeReading(overrides: Partial<MeterReadingOut> = {}): MeterReadingOut {
  return {
    id: 1,
    household_id: 1,
    submitted_by_user_id: 1,
    period: "2026-06",
    day_meter_value: "120.00",
    night_meter_value: "60.00",
    day_usage_kwh: "10.00",
    night_usage_kwh: "5.00",
    amount_charged_uah: "0.00",
    submitted_at: "2026-06-02T09:00:00.000Z",
    ...overrides,
  };
}

function mountCard(props: Partial<InstanceType<typeof MeterSubmitCard>["$props"]> = {}) {
  return mountWithPlugins(MeterSubmitCard, {
    props: {
      isOverdue: false,
      isSubmitting: false,
      isLoading: false,
      errors: {},
      dayMeterValue: null,
      nightMeterValue: null,
      latestReading: null,
      isSubmitted: false,
      ...props,
    },
    global: {
      components: { Skeleton, InputNumber, Button },
    },
  });
}

describe("MeterSubmitCard", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("renders skeleton placeholders while loading, hiding both form and submitted views", () => {
    const wrapper = mountCard({ isLoading: true });

    expect(wrapper.findAllComponents(Skeleton).length).toBeGreaterThan(0);
    expect(wrapper.find('input[type="text"], input[inputmode]').exists()).toBe(false);
    expect(wrapper.find(".submit-card__submitted-readings").exists()).toBe(false);
  });

  it("shows submitted day and night values with a submitted note when within the window", () => {
    vi.setSystemTime(new Date(2026, 5, 15));
    const reading = makeReading({
      day_meter_value: "120.00",
      night_meter_value: "60.00",
      submitted_at: new Date(2026, 5, 3, 9, 0).toISOString(),
    });

    const wrapper = mountCard({ isSubmitted: true, latestReading: reading });

    expect(wrapper.text()).toContain("120");
    expect(wrapper.text()).toContain("60");
    expect(wrapper.find(".submit-card__note--submitted").exists()).toBe(true);
    expect(wrapper.find(".submit-card__note--submitted-late").exists()).toBe(false);
  });

  it("shows a submitted-late note when the reading was submitted after the window", () => {
    vi.setSystemTime(new Date(2026, 5, 15));
    const reading = makeReading({
      submitted_at: new Date(2026, 5, 10, 9, 0).toISOString(),
    });

    const wrapper = mountCard({ isSubmitted: true, latestReading: reading });

    expect(wrapper.find(".submit-card__note--submitted-late").exists()).toBe(true);
    expect(wrapper.find(".submit-card__note--submitted").exists()).toBe(false);
  });

  it("renders labeled inputs for day and night values when not yet submitted", () => {
    const wrapper = mountCard({ isSubmitted: false });

    const labels = wrapper.findAll("label").map((l) => l.text());
    expect(labels.some((text) => /day/i.test(text))).toBe(true);
    expect(labels.some((text) => /night/i.test(text))).toBe(true);
    expect(wrapper.findAllComponents(InputNumber)).toHaveLength(2);
  });

  it("shows an overdue note (not a due note) when isOverdue is true and unsubmitted", () => {
    const wrapper = mountCard({ isSubmitted: false, isOverdue: true });

    expect(wrapper.find(".submit-card__note--overdue").exists()).toBe(true);
    expect(wrapper.find(".submit-card__note--due").exists()).toBe(false);
  });

  it("shows a due note (not overdue) when isOverdue is false and unsubmitted", () => {
    const wrapper = mountCard({ isSubmitted: false, isOverdue: false });

    expect(wrapper.find(".submit-card__note--due").exists()).toBe(true);
    expect(wrapper.find(".submit-card__note--overdue").exists()).toBe(false);
  });

  it("emits submit when the submit button is clicked", async () => {
    const wrapper = mountCard({ isSubmitted: false });

    await wrapper.findComponent(Button).trigger("click");

    expect(wrapper.emitted("submit")).toHaveLength(1);
  });

  it("[defect] ignores the caller-supplied billing month and recomputes its own, which underflows to index -1 in January", () => {
    // The page passes `billing-month-index` (computed correctly as "previous
    // month" by useMeterReadings), but MeterSubmitCard's <script setup> Props
    // interface never declares that prop -- it silently falls through as an
    // unused attribute -- and the component instead recomputes
    // `new Date().getMonth() - 1` itself. In January that's -1, an
    // out-of-bounds index into the `months.long` i18n array, so residents see
    // the literal key "months.long.-1" instead of "December" in the title.
    // This test pins that current, broken rendering; it is not a fix.
    vi.setSystemTime(new Date(2026, 0, 3)); // January 3
    const wrapper = mountCard({ isSubmitted: false });

    expect(wrapper.find("h3").text()).toContain("months.long.-1");
    expect(wrapper.find("h3").text()).not.toContain("December");
  });
});

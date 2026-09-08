import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import Skeleton from "primevue/skeleton";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mountWithPlugins } from "@/shared/testing/mount";

import MeterSubmitCard from "./MeterSubmitCard.vue";

function mountCard(props: Partial<InstanceType<typeof MeterSubmitCard>["$props"]> = {}) {
  return mountWithPlugins(MeterSubmitCard, {
    props: {
      isOverdue: false,
      isSubmitting: false,
      isLoading: false,
      errors: {},
      dayMeterValue: null,
      nightMeterValue: null,
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

  it("renders skeleton placeholders while loading, hiding the form", () => {
    const wrapper = mountCard({ isLoading: true });

    expect(wrapper.findAllComponents(Skeleton).length).toBeGreaterThan(0);
    expect(wrapper.findAllComponents(InputNumber)).toHaveLength(0);
  });

  it("renders both inputs and the primary submit label", () => {
    const wrapper = mountCard();

    const labels = wrapper.findAll("label").map((l) => l.text());
    expect(labels.some((text) => /day/i.test(text))).toBe(true);
    expect(labels.some((text) => /night/i.test(text))).toBe(true);
    expect(wrapper.findAllComponents(InputNumber)).toHaveLength(2);
    expect(wrapper.findComponent(Button).props("label")).toBe("Submit reading");
  });

  it("emits update:dayMeterValue and update:nightMeterValue when typing", () => {
    const wrapper = mountCard();
    const inputs = wrapper.findAllComponents(InputNumber);

    inputs[0]?.vm.$emit("update:modelValue", 123);
    inputs[1]?.vm.$emit("update:modelValue", 456);

    expect(wrapper.emitted("update:dayMeterValue")?.[0]).toEqual([123]);
    expect(wrapper.emitted("update:nightMeterValue")?.[0]).toEqual([456]);
  });

  it("shows the danger late-submit button and the approval note when overdue", () => {
    const wrapper = mountCard({ isOverdue: true });

    const button = wrapper.findComponent(Button);
    expect(button.props("label")).toBe("Submit late reading");
    expect(button.props("severity")).toBe("danger");
    expect(wrapper.find(".submit-card__note--overdue").exists()).toBe(true);
    expect(wrapper.text()).toContain(
      "Late submissions go to the head of the cooperative for approval and won't change this period's charge"
    );
  });

  it("swaps the submit label when isFirstPeriod is true", () => {
    const wrapper = mountCard({ isFirstPeriod: true });

    expect(wrapper.findComponent(Button).props("label")).toBe("Submit first reading");
  });

  it("renders field errors as alerts and marks the matching input invalid", () => {
    const wrapper = mountCard({
      errors: {
        dayMeterValue: "meterReadings.dayMeterValueRequired",
        nightMeterValue: "meterReadings.nightMeterValueRequired",
      },
    });

    const alerts = wrapper.findAll('[role="alert"]');
    expect(alerts).toHaveLength(2);

    const inputs = wrapper.findAllComponents(InputNumber);
    expect(inputs[0]?.props("invalid")).toBe(true);
    expect(inputs[1]?.props("invalid")).toBe(true);
  });

  it("sets the submit button's loading/aria-busy state while submitting", () => {
    const wrapper = mountCard({ isSubmitting: true });

    const button = wrapper.findComponent(Button);
    expect(button.props("loading")).toBe(true);
    expect(button.attributes("aria-busy")).toBe("true");
  });
});

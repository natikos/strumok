import { CheckCircle } from "@primeicons/vue";
import Button from "primevue/button";
import InputNumber from "primevue/inputnumber";
import Skeleton from "primevue/skeleton";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PeriodUsage } from "@/features/dashboard/composables/useUsageInsights";
import type { FieldErrors } from "@/features/dashboard/types";
import { mountWithPlugins, tUa } from "@/shared/testing/mount";
import type { DeadlineStatus } from "@shared/utils/deadline";
import { APP_LOCALE, formatMeterValue } from "@shared/utils/format";

import SubmissionCard from "./SubmissionCard.vue";

interface MountOverrides {
  locale?: "en" | "ua";
  status?: DeadlineStatus;
  daysLeft?: number;
  billingMonthIndex?: number;
  errors?: FieldErrors;
  dayMeterValue?: number | null;
  nightMeterValue?: number | null;
  isSubmitting?: boolean;
  isLoading?: boolean;
  isFirstPeriod?: boolean;
  submittedAt?: string | null;
  submittedDayValue?: number | string | null;
  submittedNightValue?: number | string | null;
  lastPeriod?: PeriodUsage | null;
  previousDayMeterValue?: number | string | null;
  previousNightMeterValue?: number | string | null;
}

function mountCard(overrides: MountOverrides = {}) {
  const { locale = "ua", ...props } = overrides;

  return mountWithPlugins(SubmissionCard, {
    props: {
      status: "due",
      daysLeft: 3,
      billingMonthIndex: 5,
      errors: {},
      dayMeterValue: null,
      nightMeterValue: null,
      isSubmitting: false,
      isLoading: false,
      ...props,
    },
    locale,
    global: {
    },
  });
}

describe("SubmissionCard", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  describe("due", () => {
    it("shows the days-left headline, the window subline, and a visible form", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard({ status: "due", daysLeft: 3 });

      expect(wrapper.find(".submission__headline").text()).toContain(tUa("deadlineStatus.daysLeft", { count: 3 }, 3));
      expect(wrapper.find(".submission__subline").text()).toContain(
        tUa("deadlineStatus.windowClosesAt", { day: 5, month: tUa("months.genitive.5") })
      );
      expect(wrapper.findAllComponents(InputNumber)).toHaveLength(2);
      expect(wrapper.find(".submission__values").exists()).toBe(false);
    });

    it("uses the default submit label and shows the hint caption, not the late note", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard({ status: "due" });

      expect(wrapper.findComponent(Button).props("label")).toBe(tUa("meterReadings.submit"));
      expect(wrapper.findComponent(Button).props("severity")).toBeFalsy();
      expect(wrapper.text()).toContain(tUa("meterReadings.hintText"));
      expect(wrapper.find(".submission__note").exists()).toBe(false);
    });
  });

  describe("period label vs deadline month", () => {
    it("names the billing period in the header and the closing month in the subline", () => {
      vi.setSystemTime(new Date(2026, 8, 17));
      const wrapper = mountCard({ status: "overdue", billingMonthIndex: 7 });

      expect(wrapper.find(".submission__period").text()).toBe(tUa("months.long.7").toUpperCase());
      expect(wrapper.find(".submission__subline").text()).toContain(tUa("months.genitive.8"));
    });

    it("keeps the two months distinct while the window is open", () => {
      vi.setSystemTime(new Date(2026, 8, 3));
      const wrapper = mountCard({ status: "due", billingMonthIndex: 7 });

      expect(wrapper.find(".submission__period").text()).toBe(tUa("months.long.7").toUpperCase());
      expect(wrapper.find(".submission__subline").text()).toContain(
        tUa("deadlineStatus.windowClosesAt", { day: 5, month: tUa("months.genitive.8") })
      );
    });

    it("uses the Ukrainian genitive month form after the deadline day", () => {
      vi.setSystemTime(new Date(2026, 8, 3));
      const wrapper = mountCard({ locale: "ua", status: "due", billingMonthIndex: 8 });

      expect(wrapper.find(".submission__subline").text()).toContain("Вікно закривається 5 вересня");
    });

    it("names the closing month in the submitted detail", () => {
      vi.setSystemTime(new Date(2026, 8, 3));
      const wrapper = mountCard({
        status: "submitted",
        billingMonthIndex: 7,
        submittedAt: "2026-09-02T10:00:00Z",
      });

      expect(wrapper.find(".submission__subline").text()).toContain("вересня");
    });
  });

  describe("overdue", () => {
    it("shows the overdue headline and keeps the form visible", () => {
      vi.setSystemTime(new Date(2026, 5, 20));
      const wrapper = mountCard({ status: "overdue", daysLeft: 0 });

      expect(wrapper.find(".submission__headline").text()).toContain(tUa("deadlineStatus.overdueHeadline"));
      expect(wrapper.findAllComponents(InputNumber)).toHaveLength(2);
      expect(wrapper.find(".submission__values").exists()).toBe(false);
    });

    it("uses a danger submit button labelled for a late submission", () => {
      vi.setSystemTime(new Date(2026, 5, 20));
      const wrapper = mountCard({ status: "overdue" });

      const button = wrapper.findComponent(Button);
      expect(button.props("label")).toBe("Надіслати запізнілі показники");
      expect(button.props("severity")).toBe("danger");
    });

    it("renders the late-submission note and hides the ordinary hint caption", () => {
      vi.setSystemTime(new Date(2026, 5, 20));
      const wrapper = mountCard({ status: "overdue" });

      expect(wrapper.find(".submission__note").exists()).toBe(true);
      expect(wrapper.text()).toContain(
        "Запізнілі подання фіксуються лише для інформації і не змінюють нарахування за цей період"
      );
      expect(wrapper.find(".submission__caption").exists()).toBe(false);
    });
  });

  describe("submitted", () => {
    it("replaces the form with value tiles and hides the inputs", () => {
      vi.setSystemTime(new Date(2026, 5, 20));
      const wrapper = mountCard({
        status: "submitted",
        submittedAt: new Date(2026, 5, 3, 9, 0).toISOString(),
        submittedDayValue: 1234,
        submittedNightValue: 56,
      });

      expect(wrapper.find(".submission__values").exists()).toBe(true);
      expect(wrapper.findAllComponents(InputNumber)).toHaveLength(0);
      expect(wrapper.text()).toContain(formatMeterValue(1234, APP_LOCALE));
      expect(wrapper.text()).toContain("56");
    });

    it("shows the submitted headline and reading-submitted icon", () => {
      vi.setSystemTime(new Date(2026, 5, 20));
      const wrapper = mountCard({
        status: "submitted",
        submittedAt: new Date(2026, 5, 3, 9, 0).toISOString(),
      });

      expect(wrapper.find(".submission__headline").text()).toContain("Показники надіслано");
      expect(wrapper.findComponent(CheckCircle).exists()).toBe(true);
    });
  });

  describe("submitted-late", () => {
    it("shows the submitted headline with the late-detail subline and value tiles", () => {
      vi.setSystemTime(new Date(2026, 5, 20));
      const wrapper = mountCard({
        status: "submitted-late",
        submittedAt: new Date(2026, 5, 10, 9, 0).toISOString(),
        submittedDayValue: 120,
        submittedNightValue: 60,
      });

      expect(wrapper.find(".submission__headline").text()).toContain("Показники надіслано");
      expect(wrapper.find(".submission__subline").text()).toContain(tUa("deadlineStatus.submittedLateDetail"));
      expect(wrapper.find(".submission__values").exists()).toBe(true);
      expect(wrapper.findAllComponents(InputNumber)).toHaveLength(0);
    });
  });

  describe("first period", () => {
    it("shows the first-period headline and explainer instead of a countdown", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard({ status: "due", isFirstPeriod: true });

      expect(wrapper.find(".submission__headline").text()).toContain(tUa("deadlineStatus.firstPeriodHeadline"));
      expect(wrapper.find(".submission__headline").text()).not.toContain(tUa("deadlineStatus.daysLeft", { count: 3 }, 3));
      expect(wrapper.find(".submission__subline").text()).toContain(tUa("deadlineStatus.firstPeriodExplainer"));
    });

    it("uses the first-submission button label", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard({ status: "due", isFirstPeriod: true });

      expect(wrapper.findComponent(Button).props("label")).toBe("Надіслати перші показники");
    });
  });

  describe("field errors", () => {
    it("renders the day error as an alert and marks the day input invalid with a matching describedby", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard({
        errors: { dayMeterValue: "meterReadings.dayMeterValueRequired" },
      });

      const alert = wrapper.find('[role="alert"]');
      expect(alert.exists()).toBe(true);
      expect(alert.attributes("id")).toBe("submission-day-error");
      expect(alert.text()).toBe("Введіть денний показник");

      const dayInput = wrapper.findAllComponents(InputNumber)[0]!;
      expect(dayInput.props("invalid")).toBe(true);

      const describedbyId = wrapper.find('[aria-describedby="submission-day-error"]');
      expect(describedbyId.exists()).toBe(true);
      expect(wrapper.find('[aria-invalid="true"]#submission-day').exists()).toBe(true);
    });

    it("renders the night error as an alert and marks the night input invalid with a matching describedby", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard({
        errors: { nightMeterValue: "meterReadings.nightMeterValueRequired" },
      });

      const alert = wrapper.find('[role="alert"]');
      expect(alert.exists()).toBe(true);
      expect(alert.attributes("id")).toBe("submission-night-error");
      expect(alert.text()).toBe("Введіть нічний показник");

      const nightInput = wrapper.findAllComponents(InputNumber)[1]!;
      expect(nightInput.props("invalid")).toBe(true);

      expect(wrapper.find('[aria-invalid="true"]#submission-night').exists()).toBe(true);
    });

    // A rejected submit used to fail silently, leaving the form looking as if
    // nothing had happened.
    it("announces a whole-form API error above the submit button", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard({ errors: { form: "errors.periodAlreadySubmitted" } });

      const alert = wrapper.find(".submission__form-error");
      expect(alert.exists()).toBe(true);
      expect(alert.attributes("role")).toBe("alert");
      expect(alert.text()).toContain(tUa("errors.periodAlreadySubmitted"));
    });
  });

  describe("emitted events", () => {
    it("emits update:dayMeterValue and update:nightMeterValue when the inputs change", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard();
      const inputs = wrapper.findAllComponents(InputNumber);

      inputs[0]?.vm.$emit("update:modelValue", 123);
      inputs[1]?.vm.$emit("update:modelValue", 456);

      expect(wrapper.emitted("update:dayMeterValue")?.[0]).toEqual([123]);
      expect(wrapper.emitted("update:nightMeterValue")?.[0]).toEqual([456]);
    });

    it("emits submit when the submit button is clicked", async () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard();

      await wrapper.findComponent(Button).trigger("click");
      expect(wrapper.emitted("submit")).toHaveLength(1);
    });
  });

  describe("loading", () => {
    it("renders skeleton placeholders and hides the form entirely", () => {
      const wrapper = mountCard({ isLoading: true });

      expect(wrapper.findAllComponents(Skeleton).length).toBeGreaterThan(0);
      expect(wrapper.findAllComponents(InputNumber)).toHaveLength(0);
      expect(wrapper.find(".submission__headline").exists()).toBe(false);
      expect(wrapper.find(".submission__values").exists()).toBe(false);
    });
  });

  describe("accessibility", () => {
    it("keeps the status block announced as a polite live region", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard({ status: "due" });

      const status = wrapper.find('[role="status"]');
      expect(status.exists()).toBe(true);
      expect(status.attributes("aria-live")).toBe("polite");
    });
  });

  describe("kWh units", () => {
    it("shows the unit alongside the last-submitted hint for both fields", () => {
      vi.setSystemTime(new Date(2026, 5, 2));
      const wrapper = mountCard({
        status: "due",
        previousDayMeterValue: 1234.5,
        previousNightMeterValue: 60,
      });

      const hints = wrapper.findAll(".submission__field-hint").map((el) => el.text());
      expect(hints.some((text) => text.includes(tUa("units.kwh")))).toBe(true);
      expect(hints).toHaveLength(2);
      hints.forEach((text) => expect(text).toContain(tUa("units.kwh")));
    });

    it("shows a unit on every usage line inside the submitted value tiles", () => {
      vi.setSystemTime(new Date(2026, 5, 20));
      const lastPeriod: PeriodUsage = {
        period: "2026-06",
        monthLabel: "Jun",
        monthLong: "June",
        monthIndex: 5,
        dayKwh: 12.5,
        nightKwh: 3.25,
        totalKwh: 15.75,
        chargedUah: null,
      };
      const wrapper = mountCard({
        status: "submitted",
        submittedAt: new Date(2026, 5, 3, 9, 0).toISOString(),
        submittedDayValue: 120,
        submittedNightValue: 60,
        lastPeriod,
      });

      const usageLines = wrapper.findAll(".submission__value-usage").map((el) => el.text());
      expect(usageLines).toHaveLength(2);
      usageLines.forEach((text) => expect(text).toContain(tUa("units.kwh")));
    });
  });
});

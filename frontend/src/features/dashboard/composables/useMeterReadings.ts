import { capitalize } from "@utils/string";
import { format, subMonths } from "date-fns";
import { computed, ref, watch } from "vue";
import { z } from "zod";

import { useUsageInsights } from "@/features/dashboard/composables/useUsageInsights";
import type { FieldErrors } from "@/features/dashboard/types";
import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
import { useLocale } from "@/features/i18n/composables/useLocale";
import { useAsyncData } from "@/shared/composables/useAsyncData";
import { useBillingWindow } from "@/shared/composables/useBillingWindow";
import {
  formatPeriodMonth,
  currentBillingPeriod as getCurrentBillingPeriod,
} from "@/shared/utils/billing-period";
import {
  getDaysLeft,
  getDeadlineMonthIndex,
  getDeadlineStatus,
  isOverdue,
} from "@/shared/utils/deadline";
import { ApiError } from "@shared/api/client";
import {
  listMyMeterReadings,
  type MeterReadingOut,
  NO_RATE_CONFIGURED_ERROR_CODE,
  submitMyMeterReading,
} from "@shared/api/meter-readings";

export interface MeterPeriod {
  period: string;
  date: Date;
  monthLabel: string;
  monthLong: string;
  isCurrent: boolean;
  reading: MeterReadingOut | undefined;
}

const schema = z.object({
  dayMeterValue: z
    .number({ error: "meterReadings.dayMeterValueRequired" })
    .nonnegative("meterReadings.meterValueNonNegative"),
  nightMeterValue: z
    .number({ error: "meterReadings.nightMeterValueRequired" })
    .nonnegative("meterReadings.meterValueNonNegative"),
});

export function useMeterReadings() {
  const isSubmitting = ref(false);
  const errors = ref<FieldErrors>({});
  const dayMeterValue = ref<null | number>(null);
  const nightMeterValue = ref<null | number>(null);

  const { currentId } = useCurrentHousehold();
  const { intlLocale } = useLocale();
  const { window: billingWindow, load: loadBillingWindow } = useBillingWindow();

  const {
    data: readings,
    isLoading,
    execute: loadHistory,
  } = useAsyncData(() => listMyMeterReadings(currentId.value), false);

  const currentMonthStart = new Date();
  currentMonthStart.setDate(1);
  currentMonthStart.setHours(0, 0, 0, 0);

  const currentBillingPeriod = getCurrentBillingPeriod();

  const readingsByPeriod = computed(() => {
    const map = new Map<string, MeterReadingOut>();
    if (readings.value) {
      for (const reading of readings.value) {
        if (reading.id !== null) {
          map.set(reading.period, reading);
        }
      }
    }
    return map;
  });

  const slots = computed<MeterPeriod[]>(() => {
    const HISTORY_MONTHS = 24;
    const result: MeterPeriod[] = [];

    for (let offset = HISTORY_MONTHS; offset >= 1; offset -= 1) {
      const date = subMonths(currentMonthStart, offset);
      const period = format(date, "yyyy-MM");
      result.push({
        period,
        date,
        monthLabel: capitalize(formatPeriodMonth(period, intlLocale.value, { month: "short" })),
        monthLong: capitalize(formatPeriodMonth(period, intlLocale.value)),
        isCurrent: period === currentBillingPeriod,
        reading: readingsByPeriod.value.get(period),
      });
    }

    return result;
  });

  const currentMeterPeriod = computed<MeterPeriod | undefined>(() =>
    slots.value.find((slot) => slot.isCurrent)
  );

  const billingMonthIndex = computed(() => {
    if (!currentMeterPeriod.value) {
      return 0;
    }
    return currentMeterPeriod.value.date.getMonth();
  });

  const latestSubmittedReading = computed<MeterReadingOut | undefined>(() => {
    return readings.value?.find((reading) => reading.id !== null);
  });

  const daysLeft = computed<number>(() => getDaysLeft());
  const deadlineMonthIndex = computed<number>(() => getDeadlineMonthIndex());

  const deadlineStatus = computed(() =>
    getDeadlineStatus(currentMeterPeriod.value?.reading?.submitted_at, billingWindow.value?.is_open)
  );

  const isFirstPeriod = computed(
    () => (readings.value?.filter((reading) => reading.id !== null).length ?? 0) === 0
  );

  // Missing periods between the household's first submission and now.
  // The current slot is only exempt while its own submit window (days 1-5)
  // is still open — once it closes, an unsubmitted current period counts as
  // missed too, same as any other gap.
  const missedPeriods = computed(() => {
    const firstSubmittedIndex = slots.value.findIndex((slot) => slot.reading);
    if (firstSubmittedIndex === -1) {
      return 0;
    }

    const currentWindowOpen = deadlineStatus.value !== "overdue";

    return slots.value
      .slice(firstSubmittedIndex)
      .filter((slot) => !slot.reading && !(slot.isCurrent && currentWindowOpen)).length;
  });

  const insights = useUsageInsights(slots);

  async function handleSubmit(): Promise<void> {
    errors.value = {};

    const parsed = schema.safeParse({
      dayMeterValue: dayMeterValue.value,
      nightMeterValue: nightMeterValue.value,
    });

    if (!parsed.success) {
      const flat = z.flattenError(parsed.error).fieldErrors;
      const next: FieldErrors = {};
      if (flat.dayMeterValue?.[0]) {
        next.dayMeterValue = flat.dayMeterValue[0];
      }
      if (flat.nightMeterValue?.[0]) {
        next.nightMeterValue = flat.nightMeterValue[0];
      }
      errors.value = next;
      return;
    }

    isSubmitting.value = true;

    try {
      const created = await submitMyMeterReading(
        {
          period: currentBillingPeriod,
          day_meter_value: parsed.data.dayMeterValue,
          night_meter_value: parsed.data.nightMeterValue,
        },
        currentId.value
      );

      const existing = readings.value ?? [];
      const hasPeriod = existing.some((reading) => reading.period === created.period);

      readings.value = hasPeriod
        ? existing.map((reading) => (reading.period === created.period ? created : reading))
        : [created, ...existing];

      dayMeterValue.value = null;
      nightMeterValue.value = null;
    } catch (error) {
      // noRateConfigured isn't the resident's fault, so it's a neutral `info` notice, not a `form` error.
      if (error instanceof ApiError) {
        const key = `errors.${error.message}`;
        errors.value =
          error.message === NO_RATE_CONFIGURED_ERROR_CODE ? { info: key } : { form: key };
      } else if (error instanceof Error) {
        console.error(error);
        errors.value = { form: "errors.requestFailed" };
      }
    } finally {
      isSubmitting.value = false;
    }
  }

  watch(currentId, () => {
    void loadHistory();
  });

  void loadBillingWindow();

  return {
    isLoading,
    isSubmitting,
    errors,
    dayMeterValue,
    nightMeterValue,
    currentSlot: currentMeterPeriod,
    slots,
    billingMonthIndex,
    isOverdue: isOverdue(currentMeterPeriod.value?.reading?.submitted_at, billingWindow.value?.is_open),
    latestReading: latestSubmittedReading,
    daysLeft,
    deadlineMonthIndex,
    deadlineStatus,
    isFirstPeriod,
    missedPeriods,
    loadHistory,
    handleSubmit,
    ...insights,
  };
}

import { capitalize } from "@utils/string";
import { computed, ref, watch } from "vue";
import { z } from "zod";

import type { FieldErrors } from "@/features/dashboard/types";
import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
import { useLocale } from "@/features/i18n/composables/useLocale";
import { getSubmitWindow, isOverdue } from "@/features/meter-readings/deadline";
import { useAsyncData } from "@/shared/composables/useAsyncData";
import { ApiError } from "@shared/api/client";
import {
  listMyMeterReadings,
  type MeterReadingOut,
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

function periodKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
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

  const {
    data: readings,
    isLoading,
    execute: loadHistory,
  } = useAsyncData(() => listMyMeterReadings(currentId.value), false);

  const currentMonthStart = new Date();
  currentMonthStart.setDate(1);
  currentMonthStart.setHours(0, 0, 0, 0);

  const previousMonthStart = new Date(currentMonthStart);
  previousMonthStart.setMonth(previousMonthStart.getMonth() - 1);

  const currentBillingPeriod = periodKey(previousMonthStart);
  const today = new Date();

  const readingsByPeriod = computed(() => {
    const map = new Map<string, MeterReadingOut>();
    if (readings.value) {
      for (const reading of readings.value) {
        map.set(reading.period, reading);
      }
    }
    return map;
  });

  const slots = computed<MeterPeriod[]>(() => {
    const HISTORY_MONTHS = 24;
    const result: MeterPeriod[] = [];
    for (let offset = HISTORY_MONTHS; offset >= 1; offset -= 1) {
      const date = new Date(currentMonthStart);
      date.setMonth(date.getMonth() - offset);
      const period = periodKey(date);
      result.push({
        period,
        date,
        monthLabel: capitalize(
          new Intl.DateTimeFormat(intlLocale.value, { month: "short" }).format(date)
        ),
        monthLong: capitalize(
          new Intl.DateTimeFormat(intlLocale.value, { month: "long" }).format(date)
        ),
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
    if (!currentMeterPeriod.value) return 0;
    return currentMeterPeriod.value.date.getMonth();
  });

  const latestSubmittedReading = computed<MeterReadingOut | undefined>(() => {
    return readings.value?.at(0);
  });

  const { end: currentDeadlineDate } = getSubmitWindow();

  const daysLeft = computed<number>(() => {
    const diffMs = currentDeadlineDate.getTime() - today.getTime();
    return Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));
  });

  async function handleSubmit(): Promise<void> {
    errors.value = {};

    const parsed = schema.safeParse({
      dayMeterValue: dayMeterValue.value,
      nightMeterValue: nightMeterValue.value,
    });

    if (!parsed.success) {
      const flat = z.flattenError(parsed.error).fieldErrors;
      const next: FieldErrors = {};
      if (flat.dayMeterValue?.[0]) next.dayMeterValue = flat.dayMeterValue[0];
      if (flat.nightMeterValue?.[0]) next.nightMeterValue = flat.nightMeterValue[0];
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
      if (readings.value) {
        readings.value = [...readings.value, created];
      }
      dayMeterValue.value = null;
      nightMeterValue.value = null;
    } catch (error) {
      if (!(error instanceof ApiError) && error instanceof Error) {
        console.error(error);
      }
    } finally {
      isSubmitting.value = false;
    }
  }

  watch(currentId, () => {
    void loadHistory();
  });

  return {
    isLoading,
    isSubmitting,
    errors,
    dayMeterValue,
    nightMeterValue,
    currentSlot: currentMeterPeriod,
    billingMonthIndex,
    isOverdue: isOverdue(currentMeterPeriod.value?.reading?.submitted_at),
    latestReading: latestSubmittedReading,
    daysLeft,
    loadHistory,
    handleSubmit,
  };
}

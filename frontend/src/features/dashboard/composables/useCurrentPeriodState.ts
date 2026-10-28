import { computed, ref, type Ref } from "vue";

import { getCurrentPeriod, listStatements } from "@shared/api/billing";
import type { MeterReadingOut } from "@shared/api/meter-readings";
import { toDecimal } from "@shared/utils/format";

export interface EstimateSummary {
  totalUah: number;
  usageKwh: number;
}

/**
 * Whether the head has closed the period residents are submitting for, and, if
 * the household didn't submit, what it was estimated at. A closed period must
 * never look like an open form, and an estimate must never look like a
 * submission.
 */
export function useCurrentPeriodState(
  readings: Ref<MeterReadingOut[] | null | undefined>,
  householdId: Ref<number | null>
) {
  const status = ref<"closed" | "open">("open");
  const period = ref("");
  const estimate = ref<EstimateSummary | null>(null);

  const isClosed = computed(() => status.value === "closed");
  const isEstimated = computed(() =>
    (readings.value ?? []).some((r) => r.period === period.value && r.source === "estimate")
  );

  async function load(): Promise<void> {
    try {
      const current = await getCurrentPeriod();
      status.value = current.status;
      period.value = current.period;

      if (current.status !== "closed") {
        estimate.value = null;
        return;
      }

      const line = (await listStatements(householdId.value)).find(
        (item) => item.period === current.period && item.is_estimated
      );
      estimate.value = line
        ? {
            totalUah: toDecimal(line.total_uah),
            usageKwh: toDecimal(line.day_usage_kwh) + toDecimal(line.night_usage_kwh),
          }
        : null;
    } catch {
      // Without the status the dashboard behaves as before (an open form); the
      // backend still answers periodClosed on a submit.
      status.value = "open";
      estimate.value = null;
    }
  }

  return { estimate, isClosed, isEstimated, load, period };
}

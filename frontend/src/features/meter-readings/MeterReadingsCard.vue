<template>
  <!-- Submit card -->
  <Card
    class="submit-card"
    :class="{
      'submit-card--due': !currentSlot?.reading && !isOverdue,
      'submit-card--overdue': isOverdue,
      'submit-card--submitted': !!currentSlot?.reading,
    }"
  >
    <template #content>
      <!-- Submitted state -->
      <div v-if="currentSlot?.reading" class="submit-card__submitted">
        <div class="submit-card__submitted-banner">
          <i class="pi pi-check-circle submit-card__check-icon" aria-hidden="true"></i>
          <div>
            <div class="submit-card__submitted-title">
              {{ $t("meterReadings.submittedTitle", { month: currentMonthLong }) }}
            </div>
            <div class="submit-card__submitted-sub">
              {{ $t("meterReadings.submittedThankYou", { name: userName }) }}
            </div>
          </div>
        </div>
        <div class="submit-card__submitted-values">
          <span class="submit-card__meter-row">
            <span class="submit-card__zone submit-card__zone--day">
              <i class="pi pi-sun" aria-hidden="true"></i>
              {{ $t("meterReadings.day") }}
            </span>
            <span class="submit-card__meter-num">{{ formatMeterValue(currentSlot.reading.day_meter_value) }}</span>
          </span>
          <span class="submit-card__meter-row">
            <span class="submit-card__zone submit-card__zone--night">
              <i class="pi pi-moon" aria-hidden="true"></i>
              {{ $t("meterReadings.night") }}
            </span>
            <span class="submit-card__meter-num">{{ formatMeterValue(currentSlot.reading.night_meter_value) }}</span>
          </span>
        </div>
        <div v-if="currentMonthTotalUsage !== null" class="submit-card__usage-pill">
          {{ $t("meterReadings.usedThisMonth", { kwh: formatKwh(currentMonthTotalUsage) }) }}
        </div>
      </div>

      <!-- Due / Overdue state (form) -->
      <div v-else>
        <div class="submit-card__header">
          <span class="submit-card__title">
            {{ $t("meterReadings.currentMonthHeading", { month: currentMonthLong }) }}
          </span>
          <span v-if="isOverdue" class="submit-card__badge submit-card__badge--overdue">
            {{ $t("meterReadings.overdue") }}
          </span>
          <span v-else class="submit-card__badge submit-card__badge--due">
            {{ $t("meterReadings.dueNow") }}
          </span>
        </div>

        <!-- Overdue alert banner -->
        <div v-if="isOverdue" class="submit-card__overdue-banner">
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          <div>
            <strong>{{ $t("meterReadings.overdueAlert", { month: currentMonthLong }) }}</strong>
            <p class="submit-card__overdue-explanation">
              {{ $t("meterReadings.overdueExplanation", { month: currentMonthLong }) }}
            </p>
          </div>
        </div>

        <!-- Estimated charge box (overdue) -->
        <div v-if="isOverdue && estimatedKwh !== null" class="submit-card__estimate">
          <span class="submit-card__estimate-label">{{ $t("meterReadings.estimatedCharge") }}</span>
          <span class="submit-card__estimate-value">{{ formatKwh(estimatedKwh) }}</span>
          <span class="submit-card__estimate-sub">
            {{ $t("meterReadings.estimatedChargeDetail", { avg: formatKwhRaw(estimatedKwh / 1.3) }) }}
          </span>
        </div>

        <!-- Previous readings hint -->
        <div v-if="latestReading" class="submit-card__previous">
          {{
            $t("meterReadings.previousReadings", {
              day: formatMeterValue(latestReading.day_meter_value),
              night: formatMeterValue(latestReading.night_meter_value),
            })
          }}
        </div>

        <form class="submit-card__form" novalidate @submit.prevent="handleSubmit">
          <div class="submit-card__fields">
            <div class="submit-card__field">
              <label class="submit-card__field-label" for="meter-reading-day">
                <i class="pi pi-sun" aria-hidden="true"></i>
                {{ $t("meterReadings.dayMeterValue") }}
              </label>
              <InputNumber
                input-id="meter-reading-day"
                v-model="dayMeterValue"
                :min="0"
                :max-fraction-digits="2"
                :placeholder="$t('meterReadings.meterValuePlaceholder')"
                :disabled="isSubmitting"
                :invalid="Boolean(errors.dayMeterValue)"
                inputmode="numeric"
                fluid
                class="submit-card__input"
              />
              <Typography v-if="errors.dayMeterValue" variant="caption" class="submit-card__error">
                {{ $t(errors.dayMeterValue) }}
              </Typography>
            </div>
            <div class="submit-card__field">
              <label class="submit-card__field-label" for="meter-reading-night">
                <i class="pi pi-moon" aria-hidden="true"></i>
                {{ $t("meterReadings.nightMeterValue") }}
              </label>
              <InputNumber
                input-id="meter-reading-night"
                v-model="nightMeterValue"
                :min="0"
                :max-fraction-digits="2"
                :placeholder="$t('meterReadings.meterValuePlaceholder')"
                :disabled="isSubmitting"
                :invalid="Boolean(errors.nightMeterValue)"
                inputmode="numeric"
                fluid
                class="submit-card__input"
              />
              <Typography v-if="errors.nightMeterValue" variant="caption" class="submit-card__error">
                {{ $t(errors.nightMeterValue) }}
              </Typography>
            </div>
          </div>

          <Button
            type="submit"
            class="submit-card__submit-btn"
            :label="isOverdue ? $t('meterReadings.submitLate') : $t('meterReadings.submit')"
            :disabled="isSubmitting"
            :loading="isSubmitting"
          />

          <p class="submit-card__hint">
            {{
              isOverdue
                ? $t("meterReadings.hintLate", { month: currentMonthLong })
                : $t("meterReadings.hintText")
            }}
          </p>
        </form>
      </div>
    </template>
  </Card>

  <!-- Stat cards row -->
  <div v-if="latestReading" class="stat-cards">
    <Card class="stat-card">
      <template #content>
        <div class="stat-card__label">{{ $t("meterReadings.usedLastMonth", { month: prevMonthShort }) }}</div>
        <div class="stat-card__value">{{ formatKwh(latestTotalUsage) }}</div>
        <div class="stat-card__sub">
          {{
            $t("meterReadings.dayNightBreakdown", {
              day: formatKwh(latestReading.day_usage_kwh),
              night: formatKwh(latestReading.night_usage_kwh),
            })
          }}
        </div>
      </template>
    </Card>
    <Card class="stat-card" :class="usageDelta ? `stat-card--${usageDelta.direction}` : ''">
      <template #content>
        <div class="stat-card__label">{{ $t("meterReadings.vsLastMonth") }}</div>
        <div
          v-if="usageDelta"
          class="stat-card__value stat-card__delta"
          :class="`stat-card__delta--${usageDelta.direction}`"
        >
          {{ usageDelta.direction === "up" ? "↑" : "↓" }}
          {{ usageDelta.percent }}%
        </div>
        <div v-else class="stat-card__value stat-card__delta--neutral">—</div>
      </template>
    </Card>
  </div>

  <!-- Meter readings card (Day + Night totals) -->
  <Card v-if="latestReading" class="meter-totals-card">
    <template #content>
      <div class="meter-totals__label">{{ $t("meterReadings.meterValues").toUpperCase() }}</div>
      <div class="meter-totals__row">
        <span class="meter-totals__zone meter-totals__zone--day">
          <i class="pi pi-sun" aria-hidden="true"></i>
          {{ $t("meterReadings.day") }}
        </span>
        <span class="meter-totals__value">{{ formatMeterValue(latestReading.day_meter_value) }}</span>
      </div>
      <div class="meter-totals__divider"></div>
      <div class="meter-totals__row">
        <span class="meter-totals__zone meter-totals__zone--night">
          <i class="pi pi-moon" aria-hidden="true"></i>
          {{ $t("meterReadings.night") }}
        </span>
        <span class="meter-totals__value">{{ formatMeterValue(latestReading.night_meter_value) }}</span>
      </div>
    </template>
  </Card>

  <!-- Trend chart -->
  <Card v-if="trendSlots.length >= 2" class="trend-card">
    <template #content>
      <div class="trend-card__header">
        <span class="trend-card__title">{{ $t("meterReadings.trendTitle") }}</span>
        <span
          v-if="trendDirection"
          class="trend-card__trend-label"
          :class="`trend-card__trend-label--${trendDirection}`"
        >
          {{ trendDirection === "down" ? $t("meterReadings.trendDecreasing") : $t("meterReadings.trendIncreasing") }}
        </span>
      </div>
      <div class="trend-chart" aria-hidden="true">
        <svg
          :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
          class="trend-chart__svg"
          preserveAspectRatio="xMidYMid meet"
        >
          <!-- Area fill -->
          <path :d="areaPath" class="trend-chart__area" />
          <!-- Line -->
          <path :d="linePath" class="trend-chart__line" />
          <!-- Dots -->
          <g v-for="(pt, i) in chartPoints" :key="i">
            <circle
              :cx="pt.x"
              :cy="pt.y"
              :class="[
                'trend-chart__dot',
                pt.isCurrent ? 'trend-chart__dot--current' : '',
              ]"
              :r="pt.isCurrent ? 6 : 4"
            />
            <!-- Ring for current -->
            <circle
              v-if="pt.isCurrent"
              :cx="pt.x"
              :cy="pt.y"
              r="10"
              class="trend-chart__dot-ring"
            />
            <!-- Callout bubble for current -->
            <g v-if="pt.isCurrent">
              <rect
                :x="pt.x - 28"
                :y="pt.y - 32"
                width="56"
                height="20"
                rx="4"
                class="trend-chart__bubble-bg"
              />
              <text
                :x="pt.x"
                :y="pt.y - 18"
                text-anchor="middle"
                class="trend-chart__bubble-text"
              >{{ pt.label }}</text>
            </g>
          </g>
          <!-- X-axis labels -->
          <text
            v-for="(pt, i) in chartPoints"
            :key="`lbl-${i}`"
            :x="pt.x"
            :y="chartHeight - 2"
            text-anchor="middle"
            :class="['trend-chart__x-label', pt.isCurrent ? 'trend-chart__x-label--current' : '']"
          >{{ pt.monthAbbr }}</text>
        </svg>
      </div>
    </template>
  </Card>

  <!-- Next deadline card (shown after submission) -->
  <Card v-if="currentSlot?.reading && nextDeadlineLabel" class="deadline-card">
    <template #content>
      <div class="deadline-card__label">{{ $t("meterReadings.nextDeadline") }}</div>
      <div class="deadline-card__value">{{ nextDeadlineLabel }}</div>
    </template>
  </Card>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";
  import { z } from "zod";

  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { ApiError } from "@shared/api/client";
  import {
    listMyMeterReadings,
    type MeterReadingOut,
    submitMyMeterReading,
  } from "@shared/api/meter-readings";

  interface Props {
    userName?: string;
  }

  const props = withDefaults(defineProps<Props>(), { userName: "" });

  interface FieldErrors {
    dayMeterValue?: string;
    nightMeterValue?: string;
  }

  interface Slot {
    period: string;
    date: Date;
    monthLabel: string;
    monthLong: string;
    isCurrent: boolean;
    reading: MeterReadingOut | undefined;
  }

  const HISTORY_MONTHS = 24;
  const TREND_MONTHS = 6;

  const readings = ref<MeterReadingOut[]>([]);
  const isSubmitting = ref(false);
  const errors = ref<FieldErrors>({});
  const dayMeterValue = ref<null | number>(null);
  const nightMeterValue = ref<null | number>(null);

  const { t } = useI18n();
  const { currentLocale } = useLocale();
  const { currentId } = useCurrentHousehold();

  const intlLocale = computed(() => (currentLocale.value === "ua" ? "uk-UA" : "en-US"));

  const currentMonthStart = (() => {
    const date = new Date();
    date.setDate(1);
    date.setHours(0, 0, 0, 0);
    return date;
  })();

  const currentPeriod = periodKey(currentMonthStart);

  // Hardcoded submission deadline: 10th of the month
  const DEADLINE_DAY = 10;
  const today = new Date();
  const isOverdue = computed(() =>
    !currentSlot.value?.reading && today.getDate() > DEADLINE_DAY,
  );

  function periodKey(date: Date): string {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  }

  function capitalize(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function totalUsage(reading: MeterReadingOut): number {
    return Number(reading.day_usage_kwh) + Number(reading.night_usage_kwh);
  }

  const readingsByPeriod = computed(() => {
    const map = new Map<string, MeterReadingOut>();
    for (const reading of readings.value) map.set(reading.period, reading);
    return map;
  });

  const slots = computed<Slot[]>(() => {
    const result: Slot[] = [];
    for (let offset = HISTORY_MONTHS; offset >= 0; offset -= 1) {
      const date = new Date(currentMonthStart);
      date.setMonth(date.getMonth() - offset);
      const period = periodKey(date);
      result.push({
        period,
        date,
        monthLabel: capitalize(
          new Intl.DateTimeFormat(intlLocale.value, { month: "short" }).format(date),
        ),
        monthLong: capitalize(
          new Intl.DateTimeFormat(intlLocale.value, { month: "long" }).format(date),
        ),
        isCurrent: period === currentPeriod,
        reading: readingsByPeriod.value.get(period),
      });
    }
    return result;
  });

  const currentSlot = computed<Slot | undefined>(() =>
    slots.value.find((slot) => slot.isCurrent),
  );

  const currentMonthLong = computed(() => currentSlot.value?.monthLong ?? "");

  const pastFilledSlots = computed<Slot[]>(() =>
    slots.value.filter((slot) => !slot.isCurrent && slot.reading),
  );

  // The "latest" reading is the most recent past reading (for stat cards and meter totals)
  const latestPastSlot = computed<Slot | undefined>(() => pastFilledSlots.value.at(-1));
  const latestReading = computed<MeterReadingOut | undefined>(() => latestPastSlot.value?.reading);

  const prevMonthShort = computed(() => latestPastSlot.value?.monthLabel ?? "");

  const latestTotalUsage = computed(() =>
    latestReading.value ? totalUsage(latestReading.value) : 0,
  );

  const currentMonthTotalUsage = computed<number | null>(() => {
    const r = currentSlot.value?.reading;
    return r ? totalUsage(r) : null;
  });

  const usageDelta = computed<
    { direction: "up" | "down"; percent: number } | undefined
  >(() => {
    const latestPast = pastFilledSlots.value.at(-1);
    const previousSlot = pastFilledSlots.value.at(-2);
    if (!latestPast?.reading || !previousSlot?.reading) return undefined;
    const current = totalUsage(latestPast.reading);
    const previous = totalUsage(previousSlot.reading);
    if (previous === 0 || Number.isNaN(current) || Number.isNaN(previous)) return undefined;
    const change = ((current - previous) / previous) * 100;
    if (Math.abs(change) < 0.5) return undefined;
    return {
      direction: change > 0 ? "up" : "down",
      percent: Math.round(Math.abs(change)),
    };
  });

  // Overdue estimate: avg of last 3 months × 1.3
  const estimatedKwh = computed<number | null>(() => {
    const last3 = pastFilledSlots.value.slice(-3);
    if (last3.length === 0) return null;
    const avg = last3.reduce((sum, s) => sum + totalUsage(s.reading!), 0) / last3.length;
    return Math.round(avg * 1.3);
  });

  // Trend chart — last 6 months of filled readings
  const trendSlots = computed(() =>
    pastFilledSlots.value.slice(-TREND_MONTHS),
  );

  const chartWidth = 300;
  const chartHeight = 100;
  const chartPadX = 24;
  const chartPadTop = 36;
  const chartPadBottom = 18;

  const chartPoints = computed(() => {
    const usages = trendSlots.value.map((s) => totalUsage(s.reading!));
    const minVal = Math.min(...usages);
    const maxVal = Math.max(...usages);
    const range = maxVal - minVal || 1;
    const n = trendSlots.value.length;
    return trendSlots.value.map((slot, i) => {
      const usage = totalUsage(slot.reading!);
      const x = chartPadX + (i / Math.max(n - 1, 1)) * (chartWidth - chartPadX * 2);
      const y =
        chartPadTop +
        (1 - (usage - minVal) / range) * (chartHeight - chartPadTop - chartPadBottom);
      return {
        x,
        y,
        isCurrent: false,
        label: `${Math.round(usage)}`,
        monthAbbr: slot.monthLabel,
      };
    });
  });

  const linePath = computed(() => {
    const pts = chartPoints.value;
    if (pts.length === 0) return "";
    return pts
      .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
      .join(" ");
  });

  const areaPath = computed(() => {
    const pts = chartPoints.value;
    if (pts.length === 0) return "";
    const bottom = chartHeight - chartPadBottom;
    const line = pts
      .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
      .join(" ");
    const firstX = pts[0]?.x ?? 0;
    const lastX = pts[pts.length - 1]?.x ?? 0;
    return `${line} L${lastX.toFixed(1)},${bottom} L${firstX.toFixed(1)},${bottom} Z`;
  });

  const trendDirection = computed<"up" | "down" | null>(() => {
    const pts = chartPoints.value;
    if (pts.length < 2) return null;
    const first = trendSlots.value[0] ? totalUsage(trendSlots.value[0].reading!) : null;
    const last = trendSlots.value.at(-1) ? totalUsage(trendSlots.value.at(-1)!.reading!) : null;
    if (first === null || last === null) return null;
    return last < first ? "down" : "up";
  });

  // Next deadline
  const nextDeadlineLabel = computed<string | null>(() => {
    const nextMonth = new Date(currentMonthStart);
    nextMonth.setMonth(nextMonth.getMonth() + 1);
    const deadlineDate = new Date(nextMonth);
    deadlineDate.setDate(DEADLINE_DAY);
    const diffMs = deadlineDate.getTime() - today.getTime();
    const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    const monthLabel = capitalize(
      new Intl.DateTimeFormat(intlLocale.value, { month: "long" }).format(nextMonth),
    );
    return t("meterReadings.nextDeadlineDetail", { month: monthLabel, days });
  });

  const schema = z.object({
    dayMeterValue: z
      .number({ error: "meterReadings.dayMeterValueRequired" })
      .nonnegative("meterReadings.meterValueNonNegative"),
    nightMeterValue: z
      .number({ error: "meterReadings.nightMeterValueRequired" })
      .nonnegative("meterReadings.meterValueNonNegative"),
  });

  function formatKwh(value: number | string): string {
    const numeric = typeof value === "string" ? Number(value) : value;
    return `${numeric.toLocaleString(intlLocale.value, { maximumFractionDigits: 2 })} ${t("units.kwh")}`;
  }

  function formatKwhRaw(value: number): string {
    return Math.round(value).toLocaleString(intlLocale.value);
  }

  function formatMeterValue(value: number | string): string {
    const numeric = typeof value === "string" ? Number(value) : value;
    return numeric.toLocaleString(intlLocale.value, { maximumFractionDigits: 2 });
  }

  async function loadHistory(): Promise<void> {
    try {
      readings.value = await listMyMeterReadings(currentId.value);
    } catch {
      // Errors surface via global toast.
    }
  }

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
          period: currentPeriod,
          day_meter_value: parsed.data.dayMeterValue,
          night_meter_value: parsed.data.nightMeterValue,
        },
        currentId.value,
      );
      readings.value = [...readings.value, created];
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

  onMounted(loadHistory);

  watch(currentId, () => {
    void loadHistory();
  });
</script>

<style scoped lang="scss">
  /* ── Submit card ─────────────────────────────────── */
  .submit-card {
    width: 100%;
    border: 2px solid #378add;

    &--overdue {
      border-color: #e24b4a;
    }

    &--submitted {
      border-color: #639922;
    }
  }

  .submit-card__header {
    display: flex;
    align-items: center;
    gap: var(--s-app-space-2);
    flex-wrap: wrap;
    margin-bottom: var(--s-app-space-3);
  }

  .submit-card__title {
    flex: 1;
    font-size: 1.15rem;
    font-weight: 700;
    line-height: 1.3;
  }

  .submit-card__badge {
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    padding: 0.2em 0.75em;
    white-space: nowrap;

    &--due {
      background: var(--color-background-warning, #fef3c7);
      color: #92400e;
    }

    &--overdue {
      background: #fee2e2;
      color: #991b1b;
    }
  }

  .submit-card__overdue-banner {
    display: flex;
    align-items: flex-start;
    gap: var(--s-app-space-2);
    background: #fee2e2;
    border-radius: var(--s-app-radius-sm);
    padding: var(--s-app-space-3);
    margin-bottom: var(--s-app-space-3);
    color: #991b1b;

    .pi {
      font-size: 1.2rem;
      flex-shrink: 0;
      margin-top: 0.1em;
    }

    strong {
      display: block;
      font-size: 1rem;
    }
  }

  .submit-card__overdue-explanation {
    margin: var(--s-app-space-1) 0 0;
    font-size: 0.9rem;
    line-height: 1.4;
  }

  .submit-card__estimate {
    background: #fee2e2;
    border-radius: var(--s-app-radius-sm);
    padding: var(--s-app-space-3);
    margin-bottom: var(--s-app-space-3);
    color: #991b1b;
    @include layout.stack(var(--s-app-space-1));
  }

  .submit-card__estimate-label {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    opacity: 0.75;
  }

  .submit-card__estimate-value {
    font-size: 1.6rem;
    font-weight: 700;
    line-height: 1;
  }

  .submit-card__estimate-sub {
    font-size: 0.8rem;
    line-height: 1.4;
    opacity: 0.8;
  }

  .submit-card__previous {
    font-size: 0.9rem;
    color: color-mix(in srgb, var(--s-content-color), transparent 30%);
    margin-bottom: var(--s-app-space-3);
  }

  .submit-card__form {
    @include layout.stack(var(--s-app-space-3));
  }

  .submit-card__fields {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-app-space-3);
  }

  .submit-card__field {
    @include layout.stack(var(--s-app-space-1));
  }

  .submit-card__field-label {
    display: inline-flex;
    align-items: center;
    gap: var(--s-app-space-1);
    font-size: 0.875rem;
    font-weight: 600;
    color: color-mix(in srgb, var(--s-content-color), transparent 20%);
    padding: var(--s-app-space-1) 0;
  }

  .submit-card__input {
    :deep(input) {
      font-size: 1.25rem;
      min-height: 44px;
    }
  }

  .submit-card__submit-btn {
    width: 100%;
    font-size: 17px;
    min-height: 48px;
    background: #378add;
    border-color: #378add;
  }

  .submit-card--overdue .submit-card__submit-btn {
    background: #e24b4a;
    border-color: #e24b4a;
  }

  .submit-card__hint {
    font-size: 0.85rem;
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    margin: 0;
    line-height: 1.4;
    text-align: center;
  }

  .submit-card__error {
    color: #e24b4a;
    display: block;
  }

  /* ── Submitted state ─────────────────────────────── */
  .submit-card__submitted {
    @include layout.stack(var(--s-app-space-3));
  }

  .submit-card__submitted-banner {
    display: flex;
    align-items: flex-start;
    gap: var(--s-app-space-3);
    background: #f0fdf4;
    border-radius: var(--s-app-radius-sm);
    padding: var(--s-app-space-3);
    color: #166534;
  }

  .submit-card__check-icon {
    font-size: 2rem;
    color: #639922;
    flex-shrink: 0;
    margin-top: 0.1em;
  }

  .submit-card__submitted-title {
    font-size: 1.1rem;
    font-weight: 700;
  }

  .submit-card__submitted-sub {
    font-size: 0.9rem;
    margin-top: var(--s-app-space-1);
    opacity: 0.85;
  }

  .submit-card__submitted-values {
    @include layout.stack(var(--s-app-space-1));
  }

  .submit-card__meter-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--s-app-space-2);
  }

  .submit-card__zone {
    display: inline-flex;
    align-items: center;
    gap: var(--s-app-space-1);
    font-size: 0.9rem;
    color: color-mix(in srgb, var(--s-content-color), transparent 25%);

    &--day .pi { color: var(--s-amber-500, #f59e0b); }
    &--night .pi { color: var(--s-primary-900); }
  }

  .submit-card__meter-num {
    font-size: 1.1rem;
    font-weight: 700;
  }

  .submit-card__usage-pill {
    display: inline-block;
    background: #dcfce7;
    color: #166534;
    border-radius: 999px;
    padding: 0.3em 1em;
    font-size: 0.9rem;
    font-weight: 600;
    align-self: flex-start;
  }

  /* ── Stat cards ──────────────────────────────────── */
  .stat-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-app-space-3);
  }

  .stat-card {
    width: 100%;

    :deep(.p-card-body) {
      padding: var(--s-app-space-3);
    }
  }

  .stat-card__label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    margin-bottom: var(--s-app-space-1);
  }

  .stat-card__value {
    font-size: 1.25rem;
    font-weight: 700;
    line-height: 1.2;
  }

  .stat-card__sub {
    font-size: 0.75rem;
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    margin-top: var(--s-app-space-1);
  }

  .stat-card__delta {
    &--up { color: #e24b4a; }
    &--down { color: var(--color-text-success, #639922); }
    &--neutral { color: color-mix(in srgb, var(--s-content-color), transparent 40%); }
  }

  /* ── Meter totals card ───────────────────────────── */
  .meter-totals-card {
    width: 100%;
  }

  .meter-totals__label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    margin-bottom: var(--s-app-space-3);
  }

  .meter-totals__row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--s-app-space-2) 0;
  }

  .meter-totals__divider {
    height: 0.5px;
    background: color-mix(in srgb, var(--s-content-color), transparent 82%);
  }

  .meter-totals__zone {
    display: inline-flex;
    align-items: center;
    gap: var(--s-app-space-2);
    font-size: 1rem;
    color: color-mix(in srgb, var(--s-content-color), transparent 20%);

    .pi { font-size: 1.1rem; }
    &--day .pi { color: var(--s-amber-500, #f59e0b); }
    &--night .pi { color: var(--s-primary-900); }
  }

  .meter-totals__value {
    font-size: 22px;
    font-weight: 700;

    @media (max-width: 30rem) {
      font-size: 16px;
    }
  }

  /* ── Trend chart ─────────────────────────────────── */
  .trend-card {
    width: 100%;
  }

  .trend-card__header {
    display: flex;
    align-items: center;
    gap: var(--s-app-space-2);
    margin-bottom: var(--s-app-space-3);
    flex-wrap: wrap;
  }

  .trend-card__title {
    font-size: 1rem;
    font-weight: 700;
  }

  .trend-card__trend-label {
    font-size: 0.8rem;
    font-weight: 700;
    border-radius: 999px;
    padding: 0.2em 0.75em;

    &--down {
      background: #f0fdf4;
      color: #166534;
    }

    &--up {
      background: #fee2e2;
      color: #991b1b;
    }
  }

  .trend-chart {
    width: 100%;
  }

  .trend-chart__svg {
    width: 100%;
    height: auto;
    display: block;
    overflow: visible;
  }

  .trend-chart__area {
    fill: #378add;
    opacity: 0.1;
  }

  .trend-chart__line {
    fill: none;
    stroke: #378add;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .trend-chart__dot {
    fill: #378add;

    &--current {
      fill: #378add;
    }
  }

  .trend-chart__dot-ring {
    fill: none;
    stroke: #378add;
    stroke-width: 1.5;
    opacity: 0.35;
  }

  .trend-chart__bubble-bg {
    fill: #378add;
  }

  .trend-chart__bubble-text {
    fill: white;
    font-size: 9px;
    font-weight: 700;
  }

  .trend-chart__x-label {
    font-size: 9px;
    fill: color-mix(in srgb, var(--s-content-color, #333), transparent 40%);

    &--current {
      fill: #378add;
      font-weight: 700;
    }
  }

  /* ── Deadline card ───────────────────────────────── */
  .deadline-card {
    width: 100%;
  }

  .deadline-card__label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    margin-bottom: var(--s-app-space-1);
  }

  .deadline-card__value {
    font-size: 1.15rem;
    font-weight: 700;
  }

  /* ── Mobile adjustments ──────────────────────────── */
  @media (max-width: 30rem) {
    .submit-card__fields {
      grid-template-columns: 1fr;
    }

    .stat-cards {
      grid-template-columns: 1fr 1fr;
    }
  }
</style>

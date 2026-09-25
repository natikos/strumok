<template>
  <div class="usage-history">
    <header class="usage-history__header">
      <h1 class="usage-history__title">{{ $t("usageHistory.title") }}</h1>
    </header>

    <section
      v-if="!isLoading && summary"
      class="usage-history__summary"
      :aria-label="$t('usageHistory.summaryAria')"
    >
      <div class="usage-history__summary-cell">
        <span class="usage-history__summary-label">
          {{ $t("usageHistory.summaryMonths", { count: summary.monthCount }) }}
        </span>
        <span class="usage-history__summary-value">
          {{ formatKwh(summary.totalUsage) }}
        </span>
      </div>
      <div class="usage-history__summary-cell">
        <span class="usage-history__summary-label">
          {{ $t("usageHistory.summaryCharged") }}
        </span>
        <span class="usage-history__summary-value">
          {{ formatUah(summary.totalCharged) }}
        </span>
      </div>
    </section>

    <section v-if="!isLoading && submissionRecord.total > 0" class="usage-history__record">
      <header class="usage-history__record-header">
        <h2 class="usage-history__record-title">{{ $t("usageHistory.recordTitle") }}</h2>
      </header>

      <p
        v-if="submissionRecord.lastState === 'missing'"
        class="usage-history__record-status usage-history__record-status--warn"
      >
        <ExclamationCircle aria-hidden="true" />
        {{ $t("usageHistory.recordMissedPeriods", { count: submissionRecord.trailingMissing }) }}
      </p>
      <p
        v-else-if="submissionRecord.lastState === 'late'"
        class="usage-history__record-status usage-history__record-status--warn"
      >
        <ExclamationCircle aria-hidden="true" />
        {{ $t("usageHistory.recordLateThisMonth") }}
      </p>
      <p v-else-if="submissionRecord.streak >= 2" class="usage-history__record-status">
        <CheckCircle aria-hidden="true" />
        {{ $t("usageHistory.recordStreak", { count: submissionRecord.streak }) }}
      </p>
      <p v-else class="usage-history__record-status">
        {{
          $t("usageHistory.recordValue", {
            onTime: submissionRecord.onTime,
            total: submissionRecord.total,
          })
        }}
      </p>

      <ul class="usage-history__record-strip" :aria-label="recordAriaLabel">
        <li v-for="entry in submissionRecord.strip" :key="entry.period">
          <button
            type="button"
            class="usage-history__record-segment"
            :class="`usage-history__record-segment--${entry.state}`"
            :aria-label="`${entry.period} — ${$t(recordStateLabelKeys[entry.state])}`"
            @click="jumpToPeriod(entry.period)"
          ></button>
        </li>
      </ul>

      <ul class="usage-history__record-legend">
        <li class="usage-history__record-legend-item">
          <span class="usage-history__record-swatch usage-history__record-swatch--on-time"></span>
          {{ $t("usageHistory.recordOnTime") }}
        </li>
        <li class="usage-history__record-legend-item">
          <span class="usage-history__record-swatch usage-history__record-swatch--late"></span>
          {{ $t("usageHistory.recordLate") }}
        </li>
        <li class="usage-history__record-legend-item">
          <span class="usage-history__record-swatch usage-history__record-swatch--missing"></span>
          {{ $t("usageHistory.recordMissing") }}
        </li>
      </ul>
    </section>

    <div v-if="!isLoading && !summary" class="usage-history__empty">
      <Inbox class="usage-history__empty-icon" aria-hidden="true" />
      <h2 class="usage-history__empty-title">{{ $t("usageHistory.emptyTitle") }}</h2>
      <p class="usage-history__empty-description">
        {{ $t("usageHistory.emptyDescription") }}
      </p>
      <div class="usage-history__empty-button">
        <Button as="router-link" :to="ROUTES.root" class="usage-history__empty-link">
          {{ $t("usageHistory.emptyCta") }}
          <ArrowRight aria-hidden="true" />
        </Button>
      </div>
    </div>

    <template v-else>
      <section v-for="group in groups" :key="group.year" class="usage-history__group">
        <div class="usage-history__group-head">
          <h2 class="usage-history__group-year">{{ group.year }}</h2>
          <span class="usage-history__group-summary">
            <span class="usage-history__group-summary-value">
              {{ formatKwh(group.totalUsage) }}
            </span>
            <span class="usage-history__group-summary-sep" aria-hidden="true">·</span>
            <span class="usage-history__group-summary-value">
              {{ formatUah(group.totalCharged) }}
            </span>
          </span>
        </div>
        <ol class="usage-history__list">
          <li
            v-for="entry in group.entries"
            :id="`usage-history-entry-${entry.period}`"
            :key="entry.period"
            class="usage-history__item"
            :class="{
              'usage-history__item--not-submitted': !entry.submitted,
              'usage-history__item--current': entry.period === currentBillingPeriod,
            }"
          >
            <div class="usage-history__item-head">
              <span class="usage-history__month">{{ entry.monthLabel }}</span>
              <span
                v-if="!entry.submitted"
                class="usage-history__not-submitted-tag"
                :class="{
                  'usage-history__not-submitted-tag--due': entry.period === currentBillingPeriod,
                }"
              >
                <Clock aria-hidden="true" />
                {{
                  entry.period === currentBillingPeriod
                    ? $t("usageHistory.notSubmitted")
                    : $t("usageHistory.noData")
                }}
              </span>
            </div>

            <template v-if="entry.submitted">
              <div class="usage-history__metrics">
                <div
                  class="usage-history__metric"
                  :class="{ 'usage-history__metric--negative': entry.dayUsage < 0 }"
                >
                  <span class="usage-history__metric-label">
                    <Sun class="metric-icon--day" aria-hidden="true" />
                    {{ $t("usageHistory.day") }}
                  </span>
                  <span class="usage-history__metric-value">
                    {{ formatKwh(entry.dayUsage) }}
                  </span>
                </div>
                <div
                  class="usage-history__metric"
                  :class="{ 'usage-history__metric--negative': entry.nightUsage < 0 }"
                >
                  <span class="usage-history__metric-label">
                    <Moon class="metric-icon--night" aria-hidden="true" />
                    {{ $t("usageHistory.night") }}
                  </span>
                  <span class="usage-history__metric-value">
                    {{ formatKwh(entry.nightUsage) }}
                  </span>
                </div>
                <div class="usage-history__metric usage-history__metric--total">
                  <span class="usage-history__metric-label">
                    {{ $t("usageHistory.total") }}
                  </span>
                  <span class="usage-history__metric-value">
                    {{ formatKwh(entry.totalUsage) }}
                  </span>
                </div>
              </div>

              <div
                class="usage-history__charge"
                :class="{ 'usage-history__charge--credit': entry.amountCharged < 0 }"
              >
                <span class="usage-history__charge-label">
                  {{ $t("usageHistory.charged") }}
                </span>
                <span class="usage-history__charge-value">
                  {{ formatUah(entry.amountCharged) }}
                  <span v-if="entry.amountCharged < 0" class="usage-history__charge-tag">
                    {{ $t("usageHistory.credit") }}
                  </span>
                </span>
              </div>
            </template>

            <p v-else class="usage-history__not-submitted-note">
              {{
                entry.period === currentBillingPeriod
                  ? $t("usageHistory.notSubmittedDescription")
                  : $t("usageHistory.noDataDescription")
              }}
            </p>

            <Button
              v-if="!entry.submitted && entry.period === currentBillingPeriod"
              as="router-link"
              :to="ROUTES.root"
              size="small"
              class="usage-history__not-submitted-cta"
            >
              {{ $t("usageHistory.notSubmittedCta") }}
              <ArrowRight aria-hidden="true" />
            </Button>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { ArrowRight, CheckCircle, Clock, ExclamationCircle, Inbox, Moon, Sun } from "@primeicons/vue";
  import { format, subMonths } from "date-fns";
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import { useCurrentHousehold } from "@features/households/useCurrentHousehold";
  import { useLocale } from "@features/i18n/composables/useLocale";
  import { listMyMeterReadings, type MeterReadingOut } from "@shared/api/meter-readings";
  import { ROUTES } from "@shared/routing/routes";
  import { DEADLINE_DAY } from "@shared/utils/deadline";
  import {
    formatKwh as formatKwhShared,
    formatUah as formatUahShared,
    toDecimal,
  } from "@shared/utils/format";

  interface SubmissionRecordEntry {
    period: string;
    state: "on-time" | "late" | "missing";
  }

  interface HistoryEntry {
    period: string;
    year: string;
    monthLabel: string;
    dayUsage: number;
    nightUsage: number;
    totalUsage: number;
    amountCharged: number;
    submitted: boolean;
  }

  interface YearGroup {
    year: string;
    entries: HistoryEntry[];
    totalUsage: number;
    totalCharged: number;
  }

  const readings = ref<MeterReadingOut[]>([]);
  const isLoading = ref(true);

  const { t } = useI18n();
  const { intlLocale } = useLocale();
  const { currentId } = useCurrentHousehold();

  function periodToDate(period: string): Date {
    const [yearStr, monthStr] = period.split("-");
    return new Date(Number(yearStr), Number(monthStr) - 1, 1);
  }

  const currentBillingPeriod = computed(() => format(subMonths(new Date(), 1), "yyyy-MM"));

  const sortedEntries = computed<HistoryEntry[]>(() => {
    const entries = readings.value.map((reading) => {
      const date = periodToDate(reading.period);
      const dayUsage = toDecimal(reading.day_usage_kwh);
      const nightUsage = toDecimal(reading.night_usage_kwh);

      return {
        period: reading.period,
        year: String(date.getFullYear()),
        monthLabel: new Intl.DateTimeFormat(intlLocale.value, { month: "long" }).format(date),
        dayUsage,
        nightUsage,
        totalUsage: dayUsage + nightUsage,
        amountCharged: toDecimal(reading.amount_charged_uah),
        submitted: reading.id !== null,
      };
    });
    return entries.sort((a, b) => (a.period < b.period ? 1 : -1));
  });

  const groups = computed<YearGroup[]>(() => {
    const map = new Map<string, HistoryEntry[]>();
    for (const entry of sortedEntries.value) {
      const list = map.get(entry.year);
      if (list) {
        list.push(entry);
      } else {
        map.set(entry.year, [entry]);
      }
    }
    return Array.from(map, ([year, entries]) => ({
      year,
      entries,
      totalUsage: entries.reduce((sum, e) => sum + e.totalUsage, 0),
      totalCharged: entries.reduce((sum, e) => sum + e.amountCharged, 0),
    }));
  });

  const RECORD_WINDOW = 12;

  const recordStateLabelKeys: Record<SubmissionRecordEntry["state"], string> = {
    "on-time": "usageHistory.recordOnTime",
    late: "usageHistory.recordLate",
    missing: "usageHistory.recordMissing",
  };

  const submissionRecord = computed(() => {
    const sorted = [...readings.value].sort((a, b) => (a.period < b.period ? -1 : 1));

    const entries: SubmissionRecordEntry[] = sorted.map((reading) => {
      if (reading.id === null || !reading.submitted_at) {
        return { period: reading.period, state: "missing" };
      }

      // The reporting month is the one after the period: a July reading is due
      // days 1-5 of August. Submitted outside that window (before the period
      // even closed, or long after) still counts as late — there's no month
      // it could have landed in on time.
      const submittedAt = new Date(reading.submitted_at);
      const [year, month] = reading.period.split("-").map(Number);
      const dueMonth = new Date(year!, month!, 1);
      const onTime =
        submittedAt.getFullYear() === dueMonth.getFullYear() &&
        submittedAt.getMonth() === dueMonth.getMonth() &&
        submittedAt.getDate() <= DEADLINE_DAY;

      return { period: reading.period, state: onTime ? "on-time" : "late" };
    });

    const onTime = entries.filter((entry) => entry.state === "on-time").length;
    const late = entries.filter((entry) => entry.state === "late").length;

    // Current streak: consecutive on-time entries ending at the most recent
    // judged (non-missing) period. Broken by the first late or missing entry.
    let streak = 0;
    for (let i = entries.length - 1; i >= 0; i -= 1) {
      if (entries[i]!.state !== "on-time") {
        break;
      }
      streak += 1;
    }

    const lastEntry = entries.at(-1);
    const lastState = lastEntry?.state ?? null;

    // How many consecutive periods, ending at the most recent, are missing.
    let trailingMissing = 0;
    for (let i = entries.length - 1; i >= 0; i -= 1) {
      if (entries[i]!.state !== "missing") {
        break;
      }
      trailingMissing += 1;
    }

    return {
      onTime,
      late,
      // Only periods we can actually judge belong in the "x of y" ratio.
      total: onTime + late,
      entries,
      strip: entries.slice(-RECORD_WINDOW),
      streak,
      lastState,
      trailingMissing,
    };
  });

  const recordAriaLabel = computed(() =>
    t("usageHistory.recordValue", {
      onTime: submissionRecord.value.onTime,
      total: submissionRecord.value.total,
    })
  );

  const summary = computed(() => {
    const submittedEntries = sortedEntries.value.filter((entry) => entry.submitted);

    if (submittedEntries.length === 0) {
      return null;
    }

    return submittedEntries.reduce(
      (acc, entry) => ({
        monthCount: acc.monthCount + 1,
        totalUsage: acc.totalUsage + entry.totalUsage,
        totalCharged: acc.totalCharged + entry.amountCharged,
      }),
      { monthCount: 0, totalUsage: 0, totalCharged: 0 }
    );
  });

  function formatKwh(value: number): string {
    return formatKwhShared(value, intlLocale.value, t("units.kwh"));
  }

  function formatUah(value: number): string {
    return formatUahShared(value, intlLocale.value);
  }

  function jumpToPeriod(period: string): void {
    document
      .getElementById(`usage-history-entry-${period}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function loadReadings(): Promise<void> {
    isLoading.value = true;
    try {
      readings.value = await listMyMeterReadings(currentId.value);
    } finally {
      isLoading.value = false;
    }
  }

  onMounted(loadReadings);

  watch(currentId, () => {
    void loadReadings();
  });
</script>

<style scoped lang="scss">
  .usage-history__header {
    margin-bottom: var(--s-app-space-5);
  }

  .usage-history__title {
    color: var(--s-content-color);
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0;
  }

  .usage-history__summary {
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    display: grid;
    gap: var(--s-app-space-3);
    grid-template-columns: 1fr 1fr;
    margin-bottom: var(--s-app-space-5);
    padding: var(--s-app-space-4);
  }

  .usage-history__summary-cell {
    @include layout.stack(0.25rem);
    min-width: 0;
  }

  .usage-history__summary-label {
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    font-size: 0.75rem;
    text-transform: uppercase;
  }

  .usage-history__summary-value {
    color: var(--s-content-color);
    font-size: 1.25rem;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
  }

  .usage-history__record {
    @include layout.stack(var(--s-app-space-3));
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    margin-bottom: var(--s-app-space-5);
    padding: var(--s-app-space-4);
  }

  .usage-history__record-header {
    align-items: baseline;
    display: flex;
    gap: var(--s-app-space-2);
    justify-content: space-between;
  }

  .usage-history__record-title {
    color: var(--s-content-color);
    font-size: 1rem;
    font-weight: 700;
    margin: 0;
  }

  .usage-history__record-value {
    color: var(--s-content-color);
    font-size: 0.9rem;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
    white-space: nowrap;
  }

  .usage-history__record-status {
    align-items: center;
    color: var(--s-content-color);
    column-gap: var(--s-app-space-1);
    display: inline-flex;
    font-size: 0.85rem;
    font-weight: 600;
    margin: 0;

    i {
      color: var(--s-primary-color);
    }

    &--warn i {
      color: var(--s-amber-500);
    }
  }

  .usage-history__record-strip {
    display: flex;
    gap: var(--s-app-space-1);
    list-style: none;
    margin: 0;
    padding: 0;

    li {
      display: flex;
      flex: 1;
      min-width: 0;
    }
  }

  .usage-history__record-segment {
    background: color-mix(in srgb, var(--s-content-color), transparent 94%);
    border: none;
    border-radius: 3px;
    cursor: pointer;
    height: 22px;
    padding: 0;
    width: 100%;

    &:focus-visible {
      outline: 2px solid var(--s-primary-color);
      outline-offset: 2px;
    }

    &--on-time {
      background: var(--s-primary-color);
    }

    &--late {
      background: var(--s-amber-500);
    }

    // Never submitted at all.
    &--missing {
      background: repeating-linear-gradient(
        135deg,
        color-mix(in srgb, var(--s-content-color), transparent 88%),
        color-mix(in srgb, var(--s-content-color), transparent 88%) 3px,
        color-mix(in srgb, var(--s-content-color), transparent 96%) 3px,
        color-mix(in srgb, var(--s-content-color), transparent 96%) 6px
      );
    }
  }

  .usage-history__record-legend {
    align-items: center;
    display: flex;
    gap: var(--s-app-space-3);
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .usage-history__record-legend-item {
    align-items: center;
    color: var(--s-content-secondary-color);
    display: inline-flex;
    font-size: 0.75rem;
    font-weight: 600;
    gap: var(--s-app-space-1);
  }

  .usage-history__record-swatch {
    border-radius: 0.2rem;
    flex-shrink: 0;
    height: 0.6rem;
    width: 0.6rem;

    &--on-time {
      background: var(--s-primary-color);
    }

    &--late {
      background: var(--s-amber-500);
    }

    &--missing {
      background: repeating-linear-gradient(
        135deg,
        color-mix(in srgb, var(--s-content-color), transparent 88%),
        color-mix(in srgb, var(--s-content-color), transparent 88%) 1px,
        color-mix(in srgb, var(--s-content-color), transparent 96%) 1px,
        color-mix(in srgb, var(--s-content-color), transparent 96%) 2px
      );
    }
  }

  .usage-history__empty {
    @include layout.stack(var(--s-app-space-3));
    align-items: center;
    padding: var(--s-app-space-8) var(--s-app-space-4);
    text-align: center;
  }

  .usage-history__empty-icon {
    color: color-mix(in srgb, var(--s-content-color), transparent 65%);
    font-size: 2.5rem;
  }

  .usage-history__empty-title {
    color: var(--s-content-color);
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0;
  }

  .usage-history__empty-description {
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    font-size: 0.9rem;
    margin: 0;
    max-width: 24rem;
  }

  .usage-history__group {
    @include layout.stack(var(--s-app-space-2));

    & + & {
      margin-top: var(--s-app-space-5);
    }
  }

  .usage-history__group-head {
    align-items: baseline;
    column-gap: var(--s-app-space-3);
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    margin: 0 0 var(--s-app-space-1);
  }

  .usage-history__group-year {
    color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    margin: 0;
    text-transform: uppercase;
  }

  .usage-history__group-summary {
    align-items: baseline;
    color: color-mix(in srgb, var(--s-content-color), transparent 25%);
    column-gap: var(--s-app-space-2);
    display: inline-flex;
    flex-wrap: wrap;
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }

  .usage-history__group-summary-sep {
    color: color-mix(in srgb, var(--s-content-color), transparent 60%);
  }

  .usage-history__list {
    @include layout.stack(var(--s-app-space-2));
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .usage-history__item {
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    display: grid;
    gap: var(--s-app-space-3);
    grid-template-columns: 1fr;
    padding: var(--s-app-space-4);

    @include layout.respond-to("md") {
      align-items: center;
      grid-template-columns: 7rem 1fr 9rem;
      gap: var(--s-app-space-5);
    }
  }

  .usage-history__item--not-submitted {
    border-style: dashed;
  }

  .usage-history__item--current {
    border-color: color-mix(in srgb, var(--s-primary-color), transparent 50%);
  }

  .usage-history__not-submitted-note {
    color: color-mix(in srgb, var(--s-content-color), transparent 45%);
    font-size: 0.85rem;
    margin: 0;

    @include layout.respond-to("md") {
      grid-column: 2;
    }
  }

  .usage-history__not-submitted-cta {
    justify-self: start;
    text-decoration: none;
    white-space: nowrap;

    @include layout.respond-to("md") {
      grid-column: 3;
      justify-self: end;
    }
  }

  .usage-history__item-head {
    align-items: baseline;
    column-gap: var(--s-app-space-2);
    display: flex;
    flex-wrap: wrap;
  }

  .usage-history__month {
    color: var(--s-content-color);
    font-size: 1.05rem;
    font-weight: 600;
    text-transform: capitalize;
  }

  .usage-history__not-submitted-tag {
    align-items: center;
    color: color-mix(in srgb, var(--s-content-color), transparent 50%);
    column-gap: var(--s-app-space-1);
    display: inline-flex;
    font-size: 0.75rem;
    font-weight: 500;

    &--due {
      color: var(--s-amber-500, #f59e0b);
    }

    svg {
      width: 0.8rem;
      height: 0.8rem;
    }
  }

  .usage-history__metrics {
    display: grid;
    gap: var(--s-app-space-2);
    grid-template-columns: repeat(3, 1fr);
  }

  .usage-history__metric {
    @include layout.stack(0.1rem);
    min-width: 0;
  }

  .usage-history__metric--total .usage-history__metric-value {
    font-weight: 700;
  }

  .usage-history__metric--negative .usage-history__metric-value {
    color: var(--s-primary-900);
  }

  .usage-history__metric-label {
    align-items: center;
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    column-gap: var(--s-app-space-1);
    display: inline-flex;
    font-size: 0.75rem;
    text-transform: uppercase;

    svg {
      width: 0.85rem;
      height: 0.85rem;
    }
  }

  .metric-icon--day {
    color: var(--s-amber-500, #f59e0b);
  }

  .metric-icon--night {
    color: var(--s-primary-900);
  }

  .usage-history__metric-value {
    color: var(--s-content-color);
    font-size: 0.95rem;
    font-variant-numeric: tabular-nums;
  }

  .usage-history__charge {
    @include layout.stack(0.1rem);
    align-items: flex-start;

    @include layout.respond-to("md") {
      align-items: flex-end;
      text-align: right;
    }
  }

  .usage-history__charge-label {
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    font-size: 0.75rem;
    text-transform: uppercase;
  }

  .usage-history__charge-value {
    align-items: baseline;
    color: var(--s-content-color);
    column-gap: var(--s-app-space-1);
    display: inline-flex;
    flex-wrap: wrap;
    font-size: 1.05rem;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
  }

  .usage-history__charge--credit .usage-history__charge-value {
    color: var(--s-primary-900);
  }

  .usage-history__charge-tag {
    background: color-mix(in srgb, var(--s-primary-900), transparent 85%);
    border-radius: var(--s-app-radius-sm);
    color: var(--s-primary-900);
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.1rem 0.4rem;
    text-transform: uppercase;
  }
</style>

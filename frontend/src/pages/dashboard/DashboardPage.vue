<template>
  <div class="dashboard">
    <BalanceStrip @open-history="goToHistory" />

    <div class="dashboard__top">
      <SubmissionCard
        class="dashboard__submission"
        :status="deadlineStatus"
        :days-left="daysLeft"
        :billing-month-index="billingMonthIndex"
        :errors="errors"
        :day-meter-value="dayMeterValue"
        :night-meter-value="nightMeterValue"
        :is-submitting="isSubmitting"
        :is-loading="isLoading"
        :is-first-period="isFirstPeriod"
        :submitted-at="currentSlot?.reading?.submitted_at"
        :submitted-day-value="currentSlot?.reading?.day_meter_value"
        :submitted-night-value="currentSlot?.reading?.night_meter_value"
        :last-period="lastSubmittedPeriod"
        :previous-day-meter-value="previousMeterValues.day"
        :previous-night-meter-value="previousMeterValues.night"
        :closed-note="closedNote"
        :warning="plausibilityWarning"
        :warning-acknowledged="warningAcknowledged"
        @update:day-meter-value="dayMeterValue = $event"
        @update:night-meter-value="nightMeterValue = $event"
        @submit="submitReading"
      />

      <StatTilesCard
        class="dashboard__stat-tiles"
        :last-period="lastSubmittedPeriod"
        :mom-change="momChange"
        :days-into-period="daysIntoPeriod"
        :season-comparison="seasonComparison"
        :missed-periods="missedPeriods"
        :is-loading="isLoading"
      />
    </div>

    <FirstRunGuideCard v-if="showFirstRunGuide" />

    <BillSummaryCard />

    <!-- With no readings at all there is nothing to chart, split or compare, so
         one dashed card stands in for the whole analytics block. -->
    <EmptyUsageCard v-if="showEmptyUsage" />

    <template v-else>
      <UsageChartCard :series="trendSeries" :is-loading="isLoading" />

      <div class="dashboard__insights">
        <YearOverYearCard
          :comparison="yearOverYear"
          :empty-month="yoyEmptyMonth"
          :empty-year="yoyEmptyYear"
          :is-loading="isLoading"
        />

        <DayNightSplitCard
          :split="dayNightSplit"
          :show-night-note="true"
          :is-loading="isLoading"
          @view-history="goToHistory"
        />

        <SeasonCard class="dashboard__desktop-only" :seasons="seasonAverages" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { getYear } from "date-fns";
  import { computed, onMounted, watch } from "vue";
  import { useI18n } from "vue-i18n";
  import { useRouter } from "vue-router";

  import BalanceStrip from "@/features/dashboard/components/BalanceStrip.vue";
  import BillSummaryCard from "@/features/dashboard/components/BillSummaryCard.vue";
  import DayNightSplitCard from "@/features/dashboard/components/DayNightSplitCard.vue";
  import EmptyUsageCard from "@/features/dashboard/components/EmptyUsageCard.vue";
  import FirstRunGuideCard from "@/features/dashboard/components/FirstRunGuideCard.vue";
  import SeasonCard from "@/features/dashboard/components/SeasonCard.vue";
  import StatTilesCard from "@/features/dashboard/components/StatTilesCard.vue";
  import SubmissionCard from "@/features/dashboard/components/SubmissionCard.vue";
  import UsageChartCard from "@/features/dashboard/components/UsageChartCard.vue";
  import YearOverYearCard from "@/features/dashboard/components/YearOverYearCard.vue";
  import { useCurrentPeriodState } from "@/features/dashboard/composables/useCurrentPeriodState";
  import { useMeterReadings } from "@/features/dashboard/composables/useMeterReadings.ts";
  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
  import { useLocale } from "@/features/i18n/composables/useLocale";
  import { ROUTES } from "@shared/routing/routes";
  import { periodToDate } from "@shared/utils/billing-period";
  import { formatKwh, formatUah } from "@shared/utils/format";

  const { currentId } = useCurrentHousehold();
  const { intlLocale } = useLocale();
  const router = useRouter();
  const { t } = useI18n();

  const {
    isLoading,
    isSubmitting,
    errors,
    dayMeterValue,
    nightMeterValue,
    plausibilityWarning,
    warningAcknowledged,
    currentSlot,
    slots,
    billingMonthIndex,
    daysLeft,
    deadlineStatus,
    isFirstPeriod,
    readings,
    loadHistory,
    handleSubmit,
    lastSubmittedPeriod,
    momChange,
    daysIntoPeriod,
    dayNightSplit,
    trendSeries,
    yearOverYear,
    seasonAverages,
    seasonComparison,
    submittedPeriods,
    missedPeriods,
  } = useMeterReadings();

  const periodState = useCurrentPeriodState(readings, currentId);

  // Closed beats open: residents get a plain explanation instead of a form that
  // would only answer periodClosed. An estimate says so, with its numbers.
  const closedNote = computed(() => {
    if (!periodState.isClosed.value) {
      return null;
    }

    const month = t(`months.long.${billingMonthIndex.value}`);

    if (periodState.isEstimated.value && periodState.estimate.value) {
      return t("meterReadings.periodEstimated", {
        month,
        total: formatUah(periodState.estimate.value.totalUah, intlLocale.value),
        usage: formatKwh(periodState.estimate.value.usageKwh, intlLocale.value, t("units.kwh")),
      });
    }

    return t("meterReadings.periodClosed", { month });
  });

  const hasAnyReading = computed(() => submittedPeriods.value.length > 0);

  const showFirstRunGuide = computed(() => !isLoading.value && !hasAnyReading.value);
  const showEmptyUsage = computed(() => !isLoading.value && !hasAnyReading.value);

  /** Meter values from the last submitted period, shown as the "last submitted" hint. */
  const previousMeterValues = computed(() => {
    const submitted = slots.value.filter((slot) => slot.reading);
    const last = submitted.at(-1);
    return {
      day: last?.reading?.day_meter_value ?? null,
      night: last?.reading?.night_meter_value ?? null,
    };
  });

  // The month the year-over-year card would have compared, for its empty copy.
  const yoyEmptyMonth = computed(() => {
    const index = lastSubmittedPeriod.value?.monthIndex ?? billingMonthIndex.value;
    return t(`months.long.${index}`);
  });

  const yoyEmptyYear = computed(() => {
    const period = lastSubmittedPeriod.value?.period;
    const year = getYear(period ? periodToDate(period) : new Date());
    return year - 1;
  });

  function goToHistory(): void {
    void router.push(ROUTES.history);
  }

  async function submitReading(): Promise<void> {
    await handleSubmit();
  }

  onMounted(async () => {
    await loadHistory();
    await periodState.load();
  });

  watch(currentId, () => {
    void loadHistory().then(periodState.load);
  });
</script>

<style scoped lang="scss">
  .dashboard {
    @include layout.stack(var(--s-app-space-4));

    &__top {
      @include layout.stack(var(--s-app-space-4));

      @include layout.respond-to("lg") {
        display: grid;
        grid-template-columns: 2fr 1fr;
        align-items: stretch;
      }
    }

    &__submission {
      min-width: 0;
    }

    &__stat-tiles {
      min-width: 0;
    }

    &__insights {
      display: grid;
      grid-template-columns: 1fr;
      gap: var(--s-app-space-4);

      @include layout.respond-to("lg") {
        // Six columns rather than three: a normal card takes two, so a leftover
        // pair can take three each and split the row evenly. With three columns
        // there is no way to express "half" and the pair would sit lopsided.
        grid-template-columns: repeat(6, 1fr);
        align-items: stretch;

        > * {
          grid-column: span 2;
        }

        // Never strand a card alone in a third of the row — it reads as a
        // layout mistake. One left over spans the full width; two left over
        // take half each.
        > :last-child:nth-child(3n + 1) {
          grid-column: span 6;
        }

        > :nth-last-child(2):nth-child(3n + 1),
        > :last-child:nth-child(3n + 2) {
          grid-column: span 3;
        }
      }
    }

    &__desktop-only {
      display: none;

      @include layout.respond-to("lg") {
        display: flex;
      }
    }
  }
</style>

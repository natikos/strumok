<template>
  <div class="dashboard">
    <SubmissionCard
      :status="deadlineStatus"
      :days-left="daysLeft"
      :billing-month-index="billingMonthIndex"
      :errors="errors"
      :day-meter-value="dayMeterValue"
      :night-meter-value="nightMeterValue"
      :is-submitting="isSubmitting"
      :is-loading="isLoading"
      :is-first-period="isFirstPeriod"
      :is-editing="isEditing"
      :submitted-at="currentSlot?.reading?.submitted_at"
      :submitted-day-value="currentSlot?.reading?.day_meter_value"
      :submitted-night-value="currentSlot?.reading?.night_meter_value"
      :last-period="lastSubmittedPeriod"
      :monthly-average="monthlyAverage"
      :days-into-period="daysIntoPeriod"
      :day-night-split="dayNightSplit"
      :previous-day-meter-value="previousMeterValues.day"
      :previous-night-meter-value="previousMeterValues.night"
      @update:day-meter-value="dayMeterValue = $event"
      @update:night-meter-value="nightMeterValue = $event"
      @submit="submitReading"
      @edit="startEdit"
    />

    <FirstRunGuideCard v-if="showFirstRunGuide" />

    <StatTilesCard
      :last-period="lastSubmittedPeriod"
      :mom-change="momChange"
      :days-into-period="daysIntoPeriod"
      :monthly-average="monthlyAverage"
      :missed-periods="missedPeriods"
      :is-loading="isLoading"
    />

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

        <SubmissionRecordCard
          class="dashboard__desktop-only"
          :record="submissionRecord"
          @view-history="goToHistory"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";
  import { useRouter } from "vue-router";

  import DayNightSplitCard from "@/features/dashboard/components/DayNightSplitCard.vue";
  import EmptyUsageCard from "@/features/dashboard/components/EmptyUsageCard.vue";
  import FirstRunGuideCard from "@/features/dashboard/components/FirstRunGuideCard.vue";
  import SeasonCard from "@/features/dashboard/components/SeasonCard.vue";
  import StatTilesCard from "@/features/dashboard/components/StatTilesCard.vue";
  import SubmissionCard from "@/features/dashboard/components/SubmissionCard.vue";
  import SubmissionRecordCard from "@/features/dashboard/components/SubmissionRecordCard.vue";
  import UsageChartCard from "@/features/dashboard/components/UsageChartCard.vue";
  import YearOverYearCard from "@/features/dashboard/components/YearOverYearCard.vue";
  import { useMeterReadings } from "@/features/dashboard/composables/useMeterReadings.ts";
  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
  import { ROUTES } from "@shared/routing/routes";

  const { currentId } = useCurrentHousehold();
  const router = useRouter();
  const { t } = useI18n();

  const {
    isLoading,
    isSubmitting,
    errors,
    dayMeterValue,
    nightMeterValue,
    currentSlot,
    slots,
    billingMonthIndex,
    daysLeft,
    deadlineStatus,
    isFirstPeriod,
    loadHistory,
    handleSubmit,
    lastSubmittedPeriod,
    momChange,
    daysIntoPeriod,
    dayNightSplit,
    monthlyAverage,
    trendSeries,
    yearOverYear,
    seasonAverages,
    submissionRecord,
    submittedPeriods,
  } = useMeterReadings();

  const isEditing = ref(false);

  const hasAnyReading = computed(() => submittedPeriods.value.length > 0);

  const showFirstRunGuide = computed(() => !isLoading.value && !hasAnyReading.value);
  const showEmptyUsage = computed(() => !isLoading.value && !hasAnyReading.value);

  const missedPeriods = computed(() => (deadlineStatus.value === "overdue" ? 1 : 0));

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
    const year = period ? Number(period.split("-")[0]) : new Date().getFullYear();
    return year - 1;
  });

  function goToHistory(): void {
    void router.push(ROUTES.history);
  }

  /** Editing re-opens the form pre-filled with the values already submitted. */
  function startEdit(): void {
    const reading = currentSlot.value?.reading;
    if (!reading) {
      return;
    }

    dayMeterValue.value = reading.day_meter_value == null ? null : Number(reading.day_meter_value);
    nightMeterValue.value =
      reading.night_meter_value == null ? null : Number(reading.night_meter_value);
    isEditing.value = true;
  }

  async function submitReading(): Promise<void> {
    await handleSubmit();

    // Only leave edit mode once the submission actually landed; on a validation
    // or API failure the form has to stay open with the resident's input.
    if (Object.keys(errors.value).length === 0) {
      isEditing.value = false;
    }
  }

  onMounted(loadHistory);

  watch(currentId, () => {
    isEditing.value = false;
    void loadHistory();
  });
</script>

<style scoped lang="scss">
  .dashboard {
    @include layout.stack(var(--s-app-space-4));

    &__insights {
      display: grid;
      grid-template-columns: 1fr;
      gap: var(--s-app-space-4);

      @include layout.respond-to("lg") {
        // Row 2 gives the YoY card the third column beside the chart above it;
        // row 3 is the three-up split / season / record row.
        grid-template-columns: repeat(3, 1fr);
        align-items: stretch;
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

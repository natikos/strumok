<template>
  <div class="dashboard">
    <div class="dashboard__main-grid">
      <div class="dashboard__left">
        <MeterSubmitCard
          :billing-month-index="billingMonthIndex"
          :is-loading="isLoading"
          :is-overdue="isOverdue"
          :is-submitting="isSubmitting"
          :errors="errors"
          :day-meter-value="dayMeterValue"
          :night-meter-value="nightMeterValue"
          :latest-reading="latestReading ?? null"
          :is-submitted="!!currentSlot?.reading"
          :days-left="daysLeft"
          @update:day-meter-value="dayMeterValue = $event"
          @update:night-meter-value="nightMeterValue = $event"
          @submit="handleSubmit"
        />
      </div>

      <div class="dashboard__right">
        <DeadlineStatusCard
          :status="deadlineStatus"
          :days-left="daysLeft"
          :billing-month-index="billingMonthIndex"
          :submitted-at="currentSlot?.reading?.submitted_at"
          :day-meter-value="currentSlot?.reading?.day_meter_value"
          :night-meter-value="currentSlot?.reading?.night_meter_value"
          :is-first-period="isFirstPeriod"
          :is-loading="isLoading"
        />
      </div>
    </div>

    <div>Placeholder for StatCards</div>
    <div>Placeholder for TrendCard</div>
    <div>Placeholder for UsageBreakdownCard</div>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, watch } from "vue";

  import DeadlineStatusCard from "@/features/dashboard/components/DeadlineStatusCard.vue";
  import MeterSubmitCard from "@/features/dashboard/components/MeterSubmitCard.vue";
  import { useMeterReadings } from "@/features/dashboard/composables/useMeterReadings.ts";
  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";

  const { currentId } = useCurrentHousehold();

  const {
    isLoading,
    isSubmitting,
    errors,
    dayMeterValue,
    nightMeterValue,
    currentSlot,
    billingMonthIndex,
    isOverdue,
    latestReading,
    daysLeft,
    deadlineStatus,
    isFirstPeriod,
    loadHistory,
    handleSubmit,
  } = useMeterReadings();

  onMounted(loadHistory);

  watch(currentId, () => {
    void loadHistory();
  });
</script>

<style scoped lang="scss">
  .dashboard {
    @include layout.stack(var(--s-app-space-4));

    &__main-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: var(--s-app-space-4);

      @media (min-width: 60rem) {
        grid-template-columns: 1fr 22rem;
        align-items: stretch;
      }
    }

    &__left {
      @include layout.stack(var(--s-app-space-3));
    }

    &__right {
      display: flex;
      flex-direction: column;
    }
  }
</style>

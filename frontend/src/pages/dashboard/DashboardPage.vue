<template>
  <div class="dashboard">
    <div class="dashboard__main-grid" :class="{ 'dashboard__main-grid--submitted': isSubmitted }">
      <div v-if="!isSubmitted" class="dashboard__left">
        <MeterSubmitCard
          :is-loading="isLoading"
          :is-overdue="isOverdue"
          :is-submitting="isSubmitting"
          :errors="errors"
          :day-meter-value="dayMeterValue"
          :night-meter-value="nightMeterValue"
          :is-first-period="isFirstPeriod"
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

    <div class="dashboard__placeholder">Placeholder for StatCards</div>
    <div class="dashboard__placeholder">Placeholder for TrendCard</div>
    <div class="dashboard__placeholder">Placeholder for UsageBreakdownCard</div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, watch } from "vue";

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
    daysLeft,
    deadlineStatus,
    isFirstPeriod,
    loadHistory,
    handleSubmit,
  } = useMeterReadings();

  const isSubmitted = computed(() => !!currentSlot.value?.reading);

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

      @include layout.respond-to("lg") {
        grid-template-columns: 1fr 22rem;
        align-items: stretch;
      }

      // Submitted: the form is gone, so there's nothing to put in the sidebar
      // rail — let the status card span the content width like the cards below.
      &--submitted {
        @include layout.respond-to("lg") {
          grid-template-columns: 1fr;
        }
      }
    }

    &__left {
      @include layout.stack(var(--s-app-space-3));
    }

    &__right {
      display: flex;
      flex-direction: column;
    }

    &__placeholder {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 8rem;
      border: 1px dashed var(--s-content-border-color);
      border-radius: var(--s-app-radius-lg);
      background: color-mix(in srgb, var(--s-content-color), transparent 97%);
      font-size: 0.85rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 55%);
    }
  }
</style>

<template>
  <Skeleton v-if="isLoading" height="9rem" />

  <ErrorState v-else-if="error" :message-key="error" @retry="load" />

  <section
    v-else-if="latest"
    class="bill-summary"
    :class="{ 'bill-summary--estimated': latest.isEstimated }"
    :aria-labelledby="headingId"
  >
    <header class="bill-summary__head">
      <h2 :id="headingId" class="bill-summary__amount">{{ money(latest.totalKopecks) }}</h2>
      <span v-if="latest.isEstimated" class="bill-summary__pill">
        <ExclamationTriangle aria-hidden="true" />
        {{ t("statuses.meterReading.estimated") }}
      </span>
    </header>

    <p class="bill-summary__for">
      {{ t("bill.for", { month: latest.period }) }}
      <template v-if="householdName"> · {{ householdName }}</template>
    </p>
    <p class="bill-summary__plain">
      {{ latest.isEstimated ? t("bill.plainEstimated") : t("bill.plain", { usage: usage }) }}
    </p>

    <Button
      class="bill-summary__toggle"
      severity="secondary"
      variant="text"
      :aria-expanded="isOpen"
      :label="t('bill.howCalculated')"
      @click="isOpen = !isOpen"
    />
    <BillBreakdown v-if="isOpen" :bill="latest" />

    <p v-if="provisional" class="bill-summary__provisional">
      {{ t("bill.soFar", { amount: money(provisional.totalKopecks) }) }}
    </p>
  </section>
</template>

<script setup lang="ts">
  import { ExclamationTriangle } from "@primeicons/vue";
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
  import { listAdjustments, listStatements } from "@shared/api/billing";
  import { type Bill, buildBill } from "@shared/utils/bill";
  import { formatKwh, formatUah } from "@shared/utils/format";

  import BillBreakdown from "./BillBreakdown.vue";

  const { t } = useI18n();
  const { current, currentId, households } = useCurrentHousehold();
  const locale = navigator.language;
  const headingId = "bill-summary-heading";

  const latest = ref<Bill | null>(null);
  const provisional = ref<Bill | null>(null);
  const isLoading = ref(true);
  const isOpen = ref(false);
  const error = ref<string | null>(null);

  const householdName = computed(() =>
    households.value.length > 1 ? (current.value?.name ?? "") : ""
  );
  const usage = computed(() =>
    latest.value ? formatKwh(latest.value.usageKwh, locale, t("units.kwh")) : ""
  );

  function money(kopecks: number): string {
    return formatUah(kopecks / 100, locale);
  }

  async function load(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      const [lines, adjustments] = await Promise.all([
        listStatements(currentId.value),
        listAdjustments(currentId.value),
      ]);
      const closed = lines.filter((line) => line.status === "closed");
      const newest = [...closed].sort((a, b) => (a.period < b.period ? 1 : -1))[0];
      const open = lines.find((line) => line.status === "provisional");

      latest.value = newest ? buildBill(newest, adjustments) : null;
      provisional.value = open ? buildBill(open, adjustments) : null;
    } catch {
      // A failed load is an error, never the empty state.
      latest.value = null;
      provisional.value = null;
      error.value = "errors.requestFailed";
    } finally {
      isLoading.value = false;
    }
  }

  watch(currentId, load);
  onMounted(load);
</script>

<style scoped lang="scss">
  .bill-summary {
    @include layout.stack(var(--s-app-space-2));
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    min-width: 0;
    padding: var(--s-app-space-4);

    &--estimated {
      border-color: var(--s-amber-500);
    }

    &__head {
      @include layout.row(var(--s-app-space-3), center, space-between);
    }

    &__amount {
      font-size: 1.8rem;
      margin: 0;
    }

    &__pill {
      align-items: center;
      color: var(--s-amber-500);
      display: inline-flex;
      font-size: 0.8rem;
      gap: var(--s-app-space-1);
    }

    &__for,
    &__plain,
    &__provisional {
      color: color-mix(in srgb, var(--s-content-color), transparent 30%);
      margin: 0;
    }

    &__provisional {
      font-size: 0.85rem;
    }

    &__toggle {
      align-self: flex-start;
      min-height: 44px;
    }
  }
</style>

<template>
  <section v-if="isLoading" class="bill-summary" aria-busy="true">
    <Skeleton height="1.8rem" width="45%" />
    <Skeleton height="1rem" width="65%" />
  </section>

  <ErrorState v-else-if="error" :message-key="error" @retry="load" />

  <section v-else-if="rows.length" class="bill-summary" :aria-labelledby="headingId">
    <h2 :id="headingId" class="bill-summary__amount">{{ money(totalKopecks) }}</h2>
    <p v-if="householdName" class="bill-summary__household">{{ householdName }}</p>

    <ul class="bill-summary__rows">
      <li v-for="row in rows" :key="row.period" class="bill-summary__row">
        <span class="bill-summary__period">
          {{ row.period }}
          <span v-if="row.isProvisional" class="bill-summary__tag">{{ t("bill.provisional") }}</span>
        </span>
        <span class="bill-summary__sum">{{ money(row.kopecks) }}</span>
      </li>
    </ul>

    <ShortfallNotice />
    <BankCoverageNotice />
  </section>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
  import { getBalance, listStatements } from "@shared/api/billing";
  import { formatUah, toDecimal } from "@shared/utils/format";

  const { t } = useI18n();
  const { current, currentId, households } = useCurrentHousehold();
  const locale = navigator.language;
  const headingId = "bill-summary-heading";

  interface Row {
    period: string;
    kopecks: number;
    isProvisional: boolean;
  }

  const rows = ref<Row[]>([]);
  const isLoading = ref(true);
  const error = ref<string | null>(null);

  const householdName = computed(() =>
    households.value.length > 1 ? (current.value?.name ?? "") : ""
  );
  const totalKopecks = computed(() => rows.value.reduce((sum, row) => sum + row.kopecks, 0));

  function money(kopecks: number): string {
    return formatUah(kopecks / 100, locale);
  }

  const toKopecks = (value: string): number => Math.round(toDecimal(value) * 100);

  async function load(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      const [lines, balance] = await Promise.all([
        listStatements(currentId.value),
        getBalance(currentId.value),
      ]);
      // What is still owed per closed month, then this month's running estimate.
      const owed: Row[] = balance.periods
        .map((p) => ({
          period: p.period,
          kopecks: toKopecks(p.due_uah) - toKopecks(p.paid_uah),
          isProvisional: false,
        }))
        .filter((row) => row.kopecks > 0)
        .sort((a, b) => (a.period < b.period ? 1 : -1));
      const open = lines.find((line) => line.status === "provisional");

      rows.value = open
        ? [{ period: open.period, kopecks: toKopecks(open.total_uah), isProvisional: true }, ...owed]
        : owed;
    } catch {
      // A failed load is an error, never the empty state.
      rows.value = [];
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

    &__amount {
      font-size: 1.8rem;
      margin: 0;
    }

    &__household {
      color: color-mix(in srgb, var(--s-content-color), transparent 30%);
      margin: 0;
    }

    &__rows {
      @include layout.stack(var(--s-app-space-1));
      list-style: none;
      margin: 0;
      padding: 0;
    }

    &__row {
      @include layout.row(var(--s-app-space-3), center, space-between);
      color: color-mix(in srgb, var(--s-content-color), transparent 20%);
    }

    &__period {
      min-width: 0;
    }

    &__tag {
      color: var(--s-amber-500);
      font-size: 0.8rem;
      margin-inline-start: var(--s-app-space-1);
    }

    &__sum {
      font-variant-numeric: tabular-nums;
    }
  }
</style>

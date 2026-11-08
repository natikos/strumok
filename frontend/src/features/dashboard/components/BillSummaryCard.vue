<template>
  <section class="bill-summary" :aria-label="t('balance.aria')">
    <BalanceStrip embedded @open-history="$emit('open-history')" />

    <ul v-if="rows.length" class="bill-summary__rows">
      <li v-for="row in rows" :key="row.period" class="bill-summary__row">
        <span class="bill-summary__period">
          {{ row.period }}
          <span v-if="row.isProvisional" class="bill-summary__tag">{{ t("bill.provisional") }}</span>
        </span>
        <span class="bill-summary__sum">{{ money(row.kopecks) }}</span>
      </li>
    </ul>
    <div v-else-if="isLoading" class="bill-summary__rows" aria-busy="true">
      <Skeleton height="1rem" width="65%" />
    </div>
    <ErrorState v-else-if="error" :message-key="error" @retry="load" />

    <ShortfallNotice />
    <BankCoverageNotice />
  </section>
</template>

<script setup lang="ts">
  import { onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
  import { getBalance, listStatements } from "@shared/api/billing";
  import { formatUah, toDecimal } from "@shared/utils/format";

  defineEmits<{ "open-history": [] }>();

  const { t } = useI18n();
  const { currentId, isPastOnly } = useCurrentHousehold();
  const locale = navigator.language;

  interface Row {
    period: string;
    kopecks: number;
    isProvisional: boolean;
  }

  const rows = ref<Row[]>([]);
  const isLoading = ref(true);
  const error = ref<string | null>(null);

  function money(kopecks: number): string {
    return formatUah(kopecks / 100, locale);
  }

  const toKopecks = (value: string): number => Math.round(toDecimal(value) * 100);

  async function load(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    // A former owner with no plot left has no month lines, only the balance.
    if (isPastOnly.value) {
      rows.value = [];
      isLoading.value = false;
      return;
    }

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
    @include layout.stack(var(--s-app-space-3));
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    min-width: 0;
    padding: var(--s-app-space-4);

    &__rows {
      @include layout.stack(var(--s-app-space-1));
      border-top: 1px solid var(--s-content-border-color);
      list-style: none;
      margin: 0;
      padding: var(--s-app-space-3) 0 0;
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

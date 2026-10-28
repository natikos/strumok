<template>
  <dl class="bill-breakdown">
    <div class="bill-breakdown__row">
      <dt>{{ t("bill.usage") }}</dt>
      <dd>{{ formatKwh(bill.usageKwh, locale, t("units.kwh")) }}</dd>
    </div>
    <div v-for="(row, index) in bill.rows" :key="index" class="bill-breakdown__row">
      <dt>
        {{ label(row) }}
        <span v-if="row.reason" class="bill-breakdown__reason">({{ row.reason }})</span>
      </dt>
      <dd>{{ money(row.kopecks) }}</dd>
    </div>
    <div class="bill-breakdown__row bill-breakdown__row--total">
      <dt>{{ t("bill.total") }}</dt>
      <dd>{{ money(bill.totalKopecks) }}</dd>
    </div>
  </dl>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";

  import { type Bill, type BillRow } from "@shared/utils/bill";
  import { formatKwh, formatUah } from "@shared/utils/format";

  defineProps<{ bill: Bill }>();

  const { t } = useI18n();
  const locale = navigator.language;

  function money(kopecks: number): string {
    return formatUah(kopecks / 100, locale);
  }

  // Plain words only: no "reconciliation", "pro-rata" or "loss" in resident copy.
  function label(row: BillRow): string {
    return t(`bill.rows.${row.kind}`);
  }
</script>

<style scoped lang="scss">
  .bill-breakdown {
    @include layout.stack(var(--s-app-space-2));
    margin: 0;
    min-width: 0;

    &__row {
      @include layout.row(var(--s-app-space-3), baseline, space-between);

      dt {
        min-width: 0;
      }

      dd {
        font-variant-numeric: tabular-nums;
        margin: 0;
        white-space: nowrap;
      }

      &--total {
        border-top: 1px solid var(--s-content-border-color);
        font-weight: 700;
        padding-top: var(--s-app-space-2);
      }
    }

    &__reason {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      font-size: 0.8rem;
    }
  }
</style>

<template>
  <section v-if="past.length > 0" class="past-households" :aria-label="$t('ownership.pastTitle')">
    <h2 class="past-households__title">{{ $t("ownership.pastTitle") }}</h2>

    <article v-for="item in past" :key="item.household_id" class="past-households__item">
      <header class="past-households__head">
        <h3 class="past-households__name">{{ item.household_name }}</h3>
        <span class="past-households__until">
          {{ $t("ownership.ownedUntil", { date: formatKyivDate(item.owned_until, intlLocale) }) }}
        </span>
      </header>

      <p class="past-households__balance">{{ balanceText(item.balance.balance_uah) }}</p>

      <ol v-if="item.statements.length > 0" class="past-households__list">
        <li v-for="line in item.statements" :key="line.period" class="past-households__line">
          <span>{{ formatPeriodMonth(line.period, intlLocale) }}</span>
          <span>{{ formatUah(line.total_uah, intlLocale) }}</span>
        </li>
      </ol>
      <p v-else class="past-households__none">{{ $t("ownership.noStatements") }}</p>
    </article>
  </section>
</template>

<script setup lang="ts">
  import { onMounted } from "vue";
  import { useI18n } from "vue-i18n";

  import { useHouseholdTenures } from "@features/households/useHouseholdTenures";
  import { useLocale } from "@features/i18n/composables/useLocale";
  import { formatPeriodMonth } from "@shared/utils/billing-period";
  import { formatKyivDate, formatUah, toDecimal } from "@shared/utils/format";

  const { t } = useI18n();
  const { intlLocale } = useLocale();
  const { past, load } = useHouseholdTenures();

  function balanceText(value: string): string {
    const amount = toDecimal(value);

    if (amount > 0) {
      return t("balance.owe", { amount: formatUah(amount, intlLocale.value) });
    }

    if (amount < 0) {
      return t("balance.credit", { amount: formatUah(Math.abs(amount), intlLocale.value) });
    }

    return t("balance.paidUp");
  }

  onMounted(load);
</script>

<style scoped lang="scss">
  .past-households {
    display: flex;
    flex-direction: column;
    gap: var(--s-app-space-3);
    min-width: 0;

    &__title {
      font-size: 1.1rem;
      margin: 0;
    }

    &__item {
      background: var(--s-content-background);
      border: 1px solid var(--s-content-border-color);
      border-radius: var(--s-app-radius-md);
      padding: var(--s-app-space-3) var(--s-app-space-4);
    }

    &__head {
      @include layout.row(var(--s-app-space-3), baseline);
      flex-wrap: wrap;
    }

    &__name {
      font-size: 1rem;
      margin: 0;
      min-width: 0;
    }

    &__until,
    &__none {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      font-size: 0.85rem;
    }

    &__balance {
      font-weight: 600;
      margin: var(--s-app-space-2) 0;
    }

    &__list {
      list-style: none;
      margin: 0;
      padding: 0;
    }

    &__line {
      @include layout.row(var(--s-app-space-3), center);
      justify-content: space-between;
      padding: 0.25rem 0;
    }
  }
</style>

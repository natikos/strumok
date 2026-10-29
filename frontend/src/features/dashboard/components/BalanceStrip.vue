<template>
  <section class="balance-strip" :aria-label="t('balance.aria')">
    <Skeleton v-if="isLoading" height="3rem" />

    <ErrorState v-else-if="error" :message-key="error" @retry="load" />

    <button
      v-else-if="balance || !hasCurrent"
      type="button"
      class="balance-strip__body"
      :class="`balance-strip__body--${state}`"
      @click="$emit('open-history')"
    >
      <span class="balance-strip__text">
        <CheckCircle v-if="state === 'paid'" aria-hidden="true" />
        {{ text }}
      </span>
      <span v-if="balance && balance.unpaid_months > 0" class="balance-strip__pill">
        {{ t("balance.unpaidMonths", { count: balance.unpaid_months }) }}
      </span>
      <span v-if="householdName" class="balance-strip__household">{{ householdName }}</span>
    </button>

    <template v-if="payable">
      <Button
        type="button"
        class="balance-strip__pay"
        :label="t('balance.pay')"
        @click="isPayOpen = true"
      />
      <PaySheet
        v-model:visible="isPayOpen"
        :amount="payAmount"
        :iban="paymentDetails!.iban"
        :recipient="paymentDetails!.recipient_name"
        :comment="payComment"
      />
    </template>
  </section>
</template>

<script setup lang="ts">
  import { CheckCircle } from "@primeicons/vue";
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
  import { useHouseholdTenures } from "@/features/households/useHouseholdTenures";
  import {
    type BalanceOut,
    getBalance,
    getPaymentDetails,
    type PaymentDetailsOut,
  } from "@shared/api/billing";
  import { formatUah, toDecimal } from "@shared/utils/format";
  import { paymentPurpose } from "@shared/utils/paymentPurpose";

  defineEmits<{ "open-history": [] }>();

  const { t } = useI18n();
  const { current, currentId, households, isPastOnly } = useCurrentHousehold();
  const locale = navigator.language;

  const { past, pastBalance, load: loadTenures } = useHouseholdTenures();

  const balance = ref<BalanceOut | null>(null);
  const paymentDetails = ref<PaymentDetailsOut | null>(null);
  const isPayOpen = ref(false);
  const isLoading = ref(true);
  const error = ref<string | null>(null);

  // Debt on plots the user gave up is still theirs, so it stays in the total.
  const amount = computed(() => toDecimal(balance.value?.balance_uah) + pastBalance.value);
  const state = computed<"credit" | "owe" | "paid">(() =>
    amount.value > 0 ? "owe" : amount.value < 0 ? "credit" : "paid"
  );
  // With no plot left, the gave-up plots are all there is to view and pay.
  const hasCurrent = computed(() => !isPastOnly.value);
  // Pay only the current plot's own balance (not the gave-up-plots debt shown in
  // the strip total): the head reconciles per household.
  // A credit on one gave-up plot can't settle another's debt (the head
  // reconciles per household), so only the plots that owe are paid.
  const owingPast = computed(() => past.value.filter((p) => toDecimal(p.balance.balance_uah) > 0));
  const ownBalance = computed(() =>
    hasCurrent.value
      ? toDecimal(balance.value?.balance_uah)
      : owingPast.value.reduce((sum, p) => sum + toDecimal(p.balance.balance_uah), 0)
  );
  const payable = computed(() => ownBalance.value > 0 && paymentDetails.value !== null);
  const payAmount = computed(() => ownBalance.value.toFixed(2));
  const payComment = computed(() =>
    paymentPurpose(
      t("balance.payPurposeLabel"),
      hasCurrent.value
        ? households.value.map((h) => h.id)
        : owingPast.value.map((p) => p.household_id)
    )
  );
  const householdName = computed(() =>
    households.value.length > 1 ? (current.value?.name ?? "") : ""
  );
  const text = computed(() => {
    if (state.value === "owe") {
      return t("balance.owe", { amount: formatUah(amount.value, locale) });
    }

    if (state.value === "credit") {
      return t("balance.credit", { amount: formatUah(Math.abs(amount.value), locale) });
    }

    return t("balance.paidUp");
  });

  async function load(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      [balance.value] = await Promise.all([
        hasCurrent.value ? getBalance(currentId.value) : null,
        loadTenures(),
      ]);
      // Paying is optional: if the details can't load, just hide the action.
      paymentDetails.value = await getPaymentDetails().catch(() => null);
    } catch {
      // Never fall through to "all paid up" when we simply don't know.
      balance.value = null;
      error.value = "balance.loadError";
    } finally {
      isLoading.value = false;
    }
  }

  watch(currentId, load);
  onMounted(load);
</script>

<style scoped lang="scss">
  .balance-strip {
    min-width: 0;

    &__body {
      @include layout.row(var(--s-app-space-3), center);
      background: var(--s-content-background);
      border: 1px solid var(--s-content-border-color);
      border-radius: var(--s-app-radius-md);
      color: var(--s-content-color);
      cursor: pointer;
      flex-wrap: wrap;
      font: inherit;
      min-height: 44px;
      padding: var(--s-app-space-3) var(--s-app-space-4);
      text-align: left;
      width: 100%;

      &--owe {
        border-color: var(--s-amber-500);
      }
    }

    &__pay {
      margin-top: var(--s-app-space-3);
      min-height: 44px;
      width: 100%;
    }

    &__text {
      font-weight: 600;
    }

    &__pill,
    &__household {
      font-size: 0.8rem;
    }

    &__pill {
      border: 1px solid var(--s-content-border-color);
      border-radius: 999px;
      padding: 0.1rem 0.6rem;
    }

    &__household {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    }
  }
</style>

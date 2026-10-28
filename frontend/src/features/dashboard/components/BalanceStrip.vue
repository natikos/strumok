<template>
  <section class="balance-strip" :aria-label="t('balance.aria')">
    <Skeleton v-if="isLoading" height="3rem" />

    <ErrorState v-else-if="error" :message-key="error" @retry="load" />

    <button v-else-if="balance" type="button" class="balance-strip__body" :class="`balance-strip__body--${state}`" @click="$emit('open-history')">
      <span class="balance-strip__text">
        <CheckCircle v-if="state === 'paid'" aria-hidden="true" />
        {{ text }}
      </span>
      <span v-if="balance.unpaid_months > 0" class="balance-strip__pill">
        {{ t("balance.unpaidMonths", { count: balance.unpaid_months }) }}
      </span>
      <span v-if="householdName" class="balance-strip__household">{{ householdName }}</span>
    </button>
  </section>
</template>

<script setup lang="ts">
  import { CheckCircle } from "@primeicons/vue";
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
  import { type BalanceOut, getBalance } from "@shared/api/billing";
  import { formatUah, toDecimal } from "@shared/utils/format";

  defineEmits<{ "open-history": [] }>();

  const { t } = useI18n();
  const { current, currentId, households } = useCurrentHousehold();
  const locale = navigator.language;

  const balance = ref<BalanceOut | null>(null);
  const isLoading = ref(true);
  const error = ref<string | null>(null);

  const amount = computed(() => toDecimal(balance.value?.balance_uah));
  const state = computed<"credit" | "owe" | "paid">(() =>
    amount.value > 0 ? "owe" : amount.value < 0 ? "credit" : "paid"
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
      balance.value = await getBalance(currentId.value);
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

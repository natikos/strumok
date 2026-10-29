<template>
  <section class="opening" :aria-label="t('admin.openingBalance.title')">
    <h3 class="opening__title">{{ t("admin.openingBalance.title") }}</h3>

    <Skeleton v-if="isLoading" height="3rem" />

    <template v-else-if="opening">
      <p class="opening__line">
        {{
          t("admin.openingBalance.original", {
            amount: money(opening.amount_uah),
            date: opening.as_of,
          })
        }}
      </p>
      <ul v-if="opening.corrections?.length" class="opening__corrections">
        <li v-for="correction in opening.corrections" :key="correction.id">
          {{
            t("admin.openingBalance.correctionLine", {
              amount: signed(correction.amount_uah),
              reason: correction.reason,
            })
          }}
        </li>
      </ul>
      <p v-if="opening.effective_amount_uah" class="opening__effective">
        {{ t("admin.openingBalance.effective", { amount: money(opening.effective_amount_uah) }) }}
      </p>

      <form class="opening__form" @submit.prevent="submitCorrection">
        <label :for="`opening-correction-${householdId}`">{{
          t("admin.openingBalance.correctionAmount")
        }}</label>
        <InputNumber
          v-model="amount"
          :input-id="`opening-correction-${householdId}`"
          :min-fraction-digits="2"
          :max-fraction-digits="2"
          fluid
        />
        <label :for="`opening-reason-${householdId}`">{{ t("admin.openingBalance.reason") }}</label>
        <InputText :id="`opening-reason-${householdId}`" v-model="reason" fluid :maxlength="500" />
        <Button
          type="submit"
          :disabled="isSaving || !amount || !reason.trim()"
          :loading="isSaving"
          :label="t('admin.openingBalance.correct')"
        />
      </form>
    </template>

    <template v-else>
      <p class="opening__muted">{{ t("admin.openingBalance.none") }}</p>
      <form class="opening__form" @submit.prevent="submitOpening">
        <label :for="`opening-amount-${householdId}`">{{ t("admin.openingBalance.amount") }}</label>
        <InputNumber
          v-model="amount"
          :input-id="`opening-amount-${householdId}`"
          :min-fraction-digits="2"
          :max-fraction-digits="2"
          fluid
        />
        <label :for="`opening-as-of-${householdId}`">{{ t("admin.openingBalance.asOf") }}</label>
        <InputText :id="`opening-as-of-${householdId}`" v-model="asOf" type="date" fluid />
        <Button
          type="submit"
          :disabled="isSaving || amount === null || !asOf"
          :loading="isSaving"
          :label="t('admin.openingBalance.set')"
        />
      </form>
    </template>
  </section>
</template>

<script setup lang="ts">
  import { format } from "date-fns";
  import { onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    correctOpeningBalance,
    getOpeningBalance,
    type OpeningBalanceOut,
    setOpeningBalance,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";
  import { formatUah, toDecimal } from "@shared/utils/format";

  const props = defineProps<{ householdId: number }>();
  const emit = defineEmits<{ changed: [] }>();

  const { t } = useI18n();
  const locale = navigator.language;

  const opening = ref<OpeningBalanceOut | null>(null);
  const isLoading = ref(true);
  const isSaving = ref(false);
  const amount = ref<number | null>(null);
  const reason = ref("");
  const asOf = ref(format(new Date(), "yyyy-MM-dd"));

  function money(value: string): string {
    return formatUah(value, locale);
  }

  function signed(value: string): string {
    return toDecimal(value) > 0 ? `+${money(value)}` : money(value);
  }

  async function save(request: () => Promise<OpeningBalanceOut>): Promise<void> {
    isSaving.value = true;

    try {
      opening.value = await request();
      amount.value = null;
      reason.value = "";
      emit("changed");
    } catch (caught: unknown) {
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
    } finally {
      isSaving.value = false;
    }
  }

  function submitCorrection(): Promise<void> {
    return save(() =>
      correctOpeningBalance(props.householdId, {
        amount_uah: String(amount.value),
        reason: reason.value.trim(),
      })
    );
  }

  function submitOpening(): Promise<void> {
    return save(() =>
      setOpeningBalance(props.householdId, { amount_uah: String(amount.value), as_of: asOf.value })
    );
  }

  onMounted(async () => {
    try {
      opening.value = await getOpeningBalance(props.householdId);
    } finally {
      isLoading.value = false;
    }
  });
</script>

<style scoped lang="scss">
  .opening {
    @include layout.stack(var(--s-app-space-2));
    min-width: 0;

    &__title {
      font-size: 0.95rem;
      margin: 0;
    }

    &__line,
    &__effective {
      margin: 0;
    }

    &__effective {
      font-weight: 600;
    }

    &__corrections {
      font-size: 0.85rem;
      margin: 0;
      padding-left: var(--s-app-space-4);
    }

    &__muted {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      font-size: 0.85rem;
      margin: 0;
    }

    &__form {
      @include layout.stack(var(--s-app-space-2));
      min-width: 0;
    }
  }
</style>

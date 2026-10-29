<template>
  <div class="bank">
    <p class="bank__hint">{{ t("admin.bank.hint") }}</p>
    <ErrorState v-if="error" :message-key="error" @retry="load" />

    <p v-else-if="!isLoading && !rows.length" class="bank__empty">{{ t("admin.bank.empty") }}</p>

    <ul v-else class="bank__list">
      <li v-for="row in rows" :key="row.id" class="bank__row">
        <div class="bank__summary">
          <span class="bank__amount">{{ money(row.amount_uah) }}</span>
          <span class="bank__date">{{ row.operation_date }}</span>
        </div>
        <p class="bank__payer">{{ t("admin.bank.payer", { name: row.payer_name || "—" }) }}</p>
        <p class="bank__purpose">{{ row.purpose }}</p>
        <p v-if="row.suggestions.length" class="bank__suggested">
          {{ t("admin.bank.suggested") }}:
          {{ row.suggestions.map((s) => householdName(s.household_id)).join(", ") }}
          ({{
            t(
              `admin.bank.suggestion${row.suggestions[0]?.source === "name" ? "Name" : "Reference"}`
            )
          }})
        </p>

        <div v-for="(line, index) in rowLines(row)" :key="index" class="bank__line">
          <Select
            v-model="line.householdId"
            class="bank__select"
            :options="households"
            option-label="name"
            option-value="id"
            :placeholder="t('admin.bank.household')"
            :aria-label="t('admin.bank.household')"
          />
          <InputNumber
            v-model="line.amount"
            class="bank__number"
            :min-fraction-digits="2"
            :max-fraction-digits="2"
            :aria-label="t('admin.bank.amount')"
          />
          <Button
            v-if="rowLines(row).length > 1"
            size="small"
            severity="secondary"
            :label="t('admin.bank.removeSplit')"
            @click="rowLines(row).splice(index, 1)"
          />
        </div>
        <p v-if="left(row) !== 0" class="bank__left">
          {{ t("admin.bank.sumLeft", { amount: money(String(left(row) / 100)) }) }}
        </p>

        <div class="bank__actions">
          <Button
            size="small"
            severity="secondary"
            :label="t('admin.bank.addSplit')"
            @click="rowLines(row).push({ householdId: null, amount: null })"
          />
          <Button
            size="small"
            :label="t('admin.bank.confirm')"
            :disabled="!canConfirm(row) || busyId === row.id"
            @click="askConfirm(row)"
          />
          <Button
            size="small"
            severity="secondary"
            :label="t('admin.bank.dismiss')"
            :disabled="busyId === row.id"
            @click="askDismiss(row)"
          />
          <Button
            v-for="candidate in row.link_candidates"
            :key="candidate.payment_id"
            size="small"
            severity="secondary"
            :label="
              t('admin.bank.link', {
                name: householdName(candidate.household_id),
                date: candidate.paid_on,
              })
            "
            :disabled="busyId === row.id"
            @click="askLink(row, candidate)"
          />
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
  import { useConfirm } from "primevue/useconfirm";
  import { onMounted, reactive, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    type AdminHouseholdOut,
    type BankTransactionOut,
    confirmBankTransaction,
    dismissBankTransaction,
    linkBankTransaction,
    listAdminHouseholds,
    listBankQueue,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";
  import { formatUah } from "@shared/utils/format";

  interface Line {
    householdId: number | null;
    amount: number | null;
  }

  const { t } = useI18n();
  const confirm = useConfirm();
  const locale = navigator.language;

  const rows = ref<BankTransactionOut[]>([]);
  const households = ref<AdminHouseholdOut[]>([]);
  const lines = reactive<Record<number, Line[]>>({});
  const error = ref<string | null>(null);
  const isLoading = ref(true);
  const busyId = ref<number | null>(null);

  function money(value: string): string {
    return formatUah(value, locale);
  }

  function cents(value: number | null): number {
    return Math.round((value ?? 0) * 100);
  }

  function totalCents(row: BankTransactionOut): number {
    return Math.round(Number(row.amount_uah) * 100);
  }

  function rowLines(row: BankTransactionOut): Line[] {
    return (lines[row.id] ??= []);
  }

  function left(row: BankTransactionOut): number {
    return totalCents(row) - rowLines(row).reduce((sum, line) => sum + cents(line.amount), 0);
  }

  function householdName(id: number): string {
    return households.value.find((household) => household.id === id)?.name ?? String(id);
  }

  function canConfirm(row: BankTransactionOut): boolean {
    const chosen = rowLines(row).map((line) => line.householdId);

    return (
      left(row) === 0 &&
      rowLines(row).every((line) => line.householdId !== null && cents(line.amount) > 0) &&
      new Set(chosen).size === chosen.length
    );
  }

  // A split suggestion pre-selects every household but leaves amounts for the admin.
  function prefill(row: BankTransactionOut): Line[] {
    if (row.suggestions.length > 1) {
      return row.suggestions.map((s) => ({ householdId: s.household_id, amount: null }));
    }

    return [{ householdId: row.suggested_household_id, amount: Number(row.amount_uah) }];
  }

  async function load(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      const [queue, all] = await Promise.all([listBankQueue(), listAdminHouseholds()]);
      households.value = all;
      rows.value = queue;
      for (const row of queue) {
        lines[row.id] ??= prefill(row);
      }
    } catch {
      error.value = "errors.requestFailed";
    } finally {
      isLoading.value = false;
    }
  }

  async function run(row: BankTransactionOut, action: () => Promise<void>): Promise<void> {
    busyId.value = row.id;

    try {
      await action();
    } catch (caught: unknown) {
      // ApiError is toasted globally; a 409 means the list is stale.
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
    } finally {
      busyId.value = null;
      await load();
    }
  }

  function askConfirm(row: BankTransactionOut): void {
    const summary = rowLines(row)
      .map((line) => `${householdName(line.householdId as number)} ${money(String(line.amount))}`)
      .join(", ");

    confirm.require({
      header: t("admin.bank.confirmTitle"),
      message: t("admin.bank.confirmBody", {
        amount: money(row.amount_uah),
        date: row.operation_date,
        lines: summary,
      }),
      acceptLabel: t("admin.bank.confirmAccept"),
      accept: () => {
        void run(row, async () => {
          await confirmBankTransaction(
            row.id,
            rowLines(row).map((line) => ({
              household_id: line.householdId as number,
              amount_uah: (line.amount ?? 0).toFixed(2),
            }))
          );
        });
      },
    });
  }

  function askDismiss(row: BankTransactionOut): void {
    confirm.require({
      header: t("admin.bank.dismissTitle"),
      message: t("admin.bank.dismissBody", { amount: money(row.amount_uah) }),
      acceptLabel: t("admin.bank.dismissAccept"),
      accept: () => {
        void run(row, () => dismissBankTransaction(row.id));
      },
    });
  }

  function askLink(
    row: BankTransactionOut,
    candidate: BankTransactionOut["link_candidates"][number]
  ): void {
    confirm.require({
      header: t("admin.bank.linkTitle"),
      message: t("admin.bank.linkBody", {
        amount: money(row.amount_uah),
        name: householdName(candidate.household_id),
        date: candidate.paid_on,
      }),
      acceptLabel: t("admin.bank.linkAccept"),
      accept: () => {
        void run(row, () => linkBankTransaction(row.id, candidate.payment_id));
      },
    });
  }

  onMounted(load);
</script>

<style scoped lang="scss">
  .bank {
    display: grid;
    gap: var(--s-app-space-3);
    min-width: 0;

    &__hint,
    &__payer,
    &__purpose,
    &__left,
    &__suggested {
      margin: 0;
      overflow-wrap: anywhere;
    }

    &__list {
      display: grid;
      gap: var(--s-app-space-3);
      margin: 0;
      padding: 0;
      list-style: none;
    }

    &__row {
      display: grid;
      gap: var(--s-app-space-2);
      min-width: 0;
    }

    &__summary,
    &__line,
    &__actions {
      display: flex;
      flex-wrap: wrap;
      gap: var(--s-app-space-2);
      align-items: center;
      min-width: 0;
    }

    &__amount {
      font-weight: 600;
    }

    &__select,
    &__number {
      flex: 1 1 8rem;
      min-width: 0;
    }
  }
</style>

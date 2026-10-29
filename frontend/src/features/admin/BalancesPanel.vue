<template>
  <div class="balances">
    <ExportCsvButton path="balances" />
    <ErrorState v-if="error" :message-key="error" @retry="load" />

    <template v-else-if="data">
      <p class="balances__total">
        {{ t("admin.balances.outstanding", { total: money(data.total_outstanding_uah) }) }}
      </p>

      <ul class="balances__list">
        <li v-for="row in data.households" :key="row.household_id" class="balances__row">
          <div class="balances__summary">
            <span class="balances__name">{{ row.household_name }}</span>
            <span class="balances__owner">{{ row.owner_name ?? "—" }}</span>
            <span
              class="balances__amount"
              :class="{ 'balances__amount--due': toDecimal(row.balance_uah) > 0 }"
            >
              {{ balanceText(row.balance_uah) }}
            </span>
            <span v-if="row.unpaid_months > 0" class="balances__pill">
              {{ t("admin.balances.unpaid") }}: {{ row.unpaid_months }}
            </span>
            <Button
              size="small"
              severity="secondary"
              :aria-expanded="openId === row.household_id"
              :aria-label="t('admin.balances.record', { name: row.household_name })"
              :label="t('admin.balances.record', { name: row.household_name })"
              @click="toggle(row)"
            />
          </div>

          <div v-if="openId === row.household_id" class="balances__detail">
            <form class="balances__form" @submit.prevent="submit(row)">
              <label :for="`pay-amount-${row.household_id}`">{{
                t("admin.balances.amount")
              }}</label>
              <InputNumber
                v-model="amount"
                :input-id="`pay-amount-${row.household_id}`"
                :min="0.01"
                :min-fraction-digits="2"
                :max-fraction-digits="2"
                fluid
              />
              <label :for="`pay-date-${row.household_id}`">{{ t("admin.balances.paidOn") }}</label>
              <InputText :id="`pay-date-${row.household_id}`" v-model="paidOn" type="date" fluid />
              <label>{{ t("admin.balances.method") }}</label>
              <Select
                v-model="method"
                fluid
                :options="methods"
                option-label="label"
                option-value="value"
              />
              <InputText
                v-model="note"
                fluid
                :maxlength="500"
                :placeholder="t('admin.balances.note')"
                :aria-label="t('admin.balances.note')"
              />
              <div class="balances__actions">
                <Button
                  type="submit"
                  :disabled="isSaving || !amount || !paidOn"
                  :loading="isSaving"
                  :label="t('admin.balances.save')"
                />
                <Button
                  type="button"
                  severity="secondary"
                  variant="text"
                  :label="t('admin.balances.cancel')"
                  @click="openId = null"
                />
              </div>
            </form>

            <h3 class="balances__subtitle">{{ t("admin.balances.payments") }}</h3>
            <p v-if="payments.length === 0" class="balances__muted">
              {{ t("admin.balances.noPayments") }}
            </p>
            <ul class="balances__payments">
              <li
                v-for="payment in payments"
                :key="payment.id"
                class="balances__payment"
                :class="{ 'balances__payment--voided': payment.voided_at }"
              >
                <span class="balances__payment-main">
                  {{ money(payment.amount_uah) }} · {{ payment.paid_on }} ·
                  {{ t(`admin.balances.${payment.method}`) }}
                  <template v-if="payment.note"> · {{ payment.note }}</template>
                </span>
                <span v-if="payment.voided_at" class="balances__muted">
                  {{ t("admin.balances.voided", { reason: payment.void_reason ?? "" }) }}
                </span>
                <template v-else>
                  <InputText
                    v-model="voidReasons[payment.id]"
                    fluid
                    :placeholder="t('admin.balances.voidReason')"
                    :aria-label="t('admin.balances.voidReason')"
                  />
                  <Button
                    size="small"
                    severity="danger"
                    variant="outlined"
                    :disabled="!(voidReasons[payment.id] ?? '').trim()"
                    :aria-label="
                      t('admin.balances.voidFor', {
                        amount: money(payment.amount_uah),
                        name: row.household_name,
                      })
                    "
                    :label="t('admin.balances.void')"
                    @click="askToVoid(row, payment)"
                  />
                </template>
              </li>
            </ul>
          </div>
        </li>
      </ul>
    </template>

    <Skeleton v-else-if="isLoading" height="10rem" />
  </div>
</template>

<script setup lang="ts">
  import { format } from "date-fns";
  import { useConfirm } from "primevue/useconfirm";
  import { onMounted, reactive, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    type BalancesOut,
    listAdminBalances,
    listHouseholdPayments,
    type PaymentOut,
    recordHouseholdPayment,
    voidHouseholdPayment,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";
  import { formatUah, toDecimal } from "@shared/utils/format";

  type Row = BalancesOut["households"][number];

  const { t } = useI18n();
  const confirm = useConfirm();
  const locale = navigator.language;

  const data = ref<BalancesOut | null>(null);
  const error = ref<string | null>(null);
  const isLoading = ref(true);
  const isSaving = ref(false);
  const openId = ref<number | null>(null);
  const payments = ref<PaymentOut[]>([]);
  const amount = ref<number | null>(null);
  const paidOn = ref(format(new Date(), "yyyy-MM-dd"));
  const method = ref<"cash" | "transfer">("cash");
  const note = ref("");
  const voidReasons = reactive<Record<number, string>>({});

  const methods = [
    { label: t("admin.balances.cash"), value: "cash" as const },
    { label: t("admin.balances.transfer"), value: "transfer" as const },
  ];

  function money(value: string): string {
    return formatUah(value, locale);
  }

  function balanceText(value: string): string {
    const amountValue = toDecimal(value);

    if (amountValue > 0) {
      return t("admin.balances.owes", { amount: money(value) });
    }

    if (amountValue < 0) {
      return t("admin.balances.credit", { amount: money(String(Math.abs(amountValue))) });
    }

    return t("admin.balances.settled");
  }

  async function load(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      data.value = await listAdminBalances();
    } catch {
      // An error must never read as "everyone has paid".
      error.value = "errors.requestFailed";
    } finally {
      isLoading.value = false;
    }
  }

  async function toggle(row: Row): Promise<void> {
    if (openId.value === row.household_id) {
      openId.value = null;
      return;
    }

    openId.value = row.household_id;
    amount.value = toDecimal(row.balance_uah) > 0 ? toDecimal(row.balance_uah) : null;
    note.value = "";
    payments.value = await listHouseholdPayments(row.household_id);
  }

  async function submit(row: Row): Promise<void> {
    if (!amount.value) {
      return;
    }

    isSaving.value = true;

    try {
      await recordHouseholdPayment(row.household_id, {
        amount_uah: String(amount.value),
        method: method.value,
        paid_on: paidOn.value,
        ...(note.value.trim() ? { note: note.value.trim() } : {}),
      });
      payments.value = await listHouseholdPayments(row.household_id);
      amount.value = null;
      note.value = "";
      await load();
    } catch (caught: unknown) {
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
    } finally {
      isSaving.value = false;
    }
  }

  function askToVoid(row: Row, payment: PaymentOut): void {
    const reason = (voidReasons[payment.id] ?? "").trim();

    confirm.require({
      accept: () =>
        void (async () => {
          try {
            await voidHouseholdPayment(payment.id, reason);
            payments.value = await listHouseholdPayments(row.household_id);
            await load();
          } catch (caught: unknown) {
            if (!(caught instanceof ApiError)) {
              throw caught;
            }
          }
        })(),
      acceptLabel: t("admin.balances.voidAccept"),
      header: t("admin.balances.voidTitle", {
        amount: money(payment.amount_uah),
        date: payment.paid_on,
        name: row.household_name,
      }),
      message: t("admin.balances.voidBody"),
      rejectLabel: t("admin.balances.cancel"),
    });
  }

  onMounted(load);
</script>

<style scoped lang="scss">
  .balances {
    @include layout.stack(var(--s-app-space-4));
    min-width: 0;

    &__total {
      font-weight: 600;
      margin: 0;
    }

    &__list,
    &__payments {
      @include layout.stack(var(--s-app-space-3));
      list-style: none;
      margin: 0;
      padding: 0;
    }

    &__row {
      background: var(--s-content-background);
      border: 1px solid var(--s-content-border-color);
      border-radius: var(--s-app-radius-md);
      min-width: 0;
      padding: var(--s-app-space-4);
    }

    &__summary {
      @include layout.stack(var(--s-app-space-2));

      @include layout.respond-to("md") {
        align-items: center;
        flex-direction: row;
        flex-wrap: wrap;
        gap: var(--s-app-space-4);
      }
    }

    &__name {
      font-weight: 600;
    }

    &__owner,
    &__muted {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      font-size: 0.85rem;
    }

    &__amount--due {
      color: var(--s-amber-500);
      font-weight: 600;
    }

    &__pill {
      border: 1px solid var(--s-content-border-color);
      border-radius: 999px;
      font-size: 0.75rem;
      padding: 0.1rem 0.6rem;
    }

    &__detail,
    &__form {
      @include layout.stack(var(--s-app-space-3));
      margin-top: var(--s-app-space-3);
      min-width: 0;
    }

    &__actions {
      @include layout.row(var(--s-app-space-2), center);
      flex-wrap: wrap;
    }

    &__subtitle {
      font-size: 0.95rem;
      margin: 0;
    }

    &__payment {
      @include layout.stack(var(--s-app-space-2));
      border-top: 1px solid var(--s-content-border-color);
      padding-top: var(--s-app-space-2);

      &--voided .balances__payment-main {
        text-decoration: line-through;
      }
    }
  }
</style>

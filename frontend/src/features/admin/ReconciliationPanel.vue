<template>
  <div class="reconciliation">
    <ErrorState v-if="error" :message-key="error" @retry="load" />

    <template v-else-if="data">
      <ExportCsvButton v-if="data.status === 'closed'" :path="`period/${period}`" />
      <div
        class="reconciliation__result"
        :class="{ 'reconciliation__result--ok': variantKey === 'matches' }"
        role="status"
      >
        {{ resultText }}
      </div>

      <div class="reconciliation__top">
        <div class="reconciliation__card">
          <h3 class="reconciliation__card-title">{{ t("admin.reconciliation.billCard") }}</h3>
          <div class="reconciliation__field">
            <label for="bill-day">{{ t("admin.reconciliation.dayKwh") }}</label>
            <InputNumber
              v-model="billDay"
              input-id="bill-day"
              :min="0"
              :min-fraction-digits="2"
              :max-fraction-digits="2"
              :disabled="isClosed || isSaving"
              fluid
            />
          </div>
          <div class="reconciliation__field">
            <label for="bill-night">{{ t("admin.reconciliation.nightKwh") }}</label>
            <InputNumber
              v-model="billNight"
              input-id="bill-night"
              :min="0"
              :min-fraction-digits="2"
              :max-fraction-digits="2"
              :disabled="isClosed || isSaving"
              fluid
            />
          </div>
          <div class="reconciliation__field">
            <label for="bill-total">{{ t("admin.reconciliation.totalUah") }}</label>
            <InputNumber
              v-model="billTotal"
              input-id="bill-total"
              :min="0"
              :min-fraction-digits="2"
              :max-fraction-digits="2"
              :disabled="isSaving"
              fluid
            />
          </div>
          <p v-if="isClosed" class="reconciliation__note">
            {{ t("admin.reconciliation.closedNote") }}
          </p>
          <RestatementPreview
            v-if="isClosed && correcting"
            :request="requestBillCorrection"
            @cancel="correcting = false"
            @posted="onCorrectionPosted"
          />
          <Button
            v-else-if="isClosed"
            :disabled="billTotal === null || billTotal === toDecimal(data.bill_total_uah)"
            :label="t('admin.restatement.correctBill')"
            @click="correcting = true"
          />
          <Button
            v-else
            :disabled="isSaving || !canSave"
            :loading="isSaving"
            :label="t('admin.reconciliation.saveBill')"
            @click="askToSave"
          />
        </div>

        <div class="reconciliation__tiles">
          <div class="reconciliation__tile">
            <span class="reconciliation__tile-label">{{ t("admin.reconciliation.tileBill") }}</span>
            <span class="reconciliation__tile-value">{{ uah(data.bill_total_uah) }}</span>
          </div>
          <div class="reconciliation__tile">
            <span class="reconciliation__tile-label">{{
              t("admin.reconciliation.tileUsage")
            }}</span>
            <span class="reconciliation__tile-value">{{ kwh(data.total_usage_kwh) }}</span>
          </div>
          <div class="reconciliation__tile">
            <span class="reconciliation__tile-label">{{ t("admin.reconciliation.tileLoss") }}</span>
            <span class="reconciliation__tile-value">{{ lossText }}</span>
          </div>
        </div>
      </div>

      <div class="reconciliation__table-card">
        <div class="reconciliation__scroll">
          <table class="reconciliation__table">
            <thead>
              <tr>
                <th scope="col">{{ t("admin.reconciliation.household") }}</th>
                <th scope="col">{{ t("admin.reconciliation.usage") }}</th>
                <th scope="col">{{ t("admin.reconciliation.share") }}</th>
                <th scope="col">{{ t("admin.reconciliation.tariff") }}</th>
                <th scope="col">{{ t("admin.reconciliation.lossShare") }}</th>
                <th scope="col">{{ t("admin.reconciliation.penalty") }}</th>
                <th scope="col">{{ t("admin.reconciliation.total") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="line in data.lines" :key="line.household_id">
                <th scope="row">
                  {{ line.household_name }}
                  <span v-if="line.is_estimated" class="reconciliation__tag">{{
                    t("admin.reconciliation.estimated")
                  }}</span>
                </th>
                <td>{{ kwh(line.usage_kwh) }}</td>
                <td>{{ line.usage_share_percent }}%</td>
                <td>{{ uah(line.tariff_uah) }}</td>
                <td>{{ data.bill_total_uah === null ? "—" : uah(line.loss_share_uah) }}</td>
                <td>{{ uah(line.penalty_uah) }}</td>
                <td>{{ data.bill_total_uah === null ? "—" : uah(line.total_uah) }}</td>
              </tr>
              <tr v-if="data.lines.length === 0">
                <td class="reconciliation__empty" colspan="7">
                  {{ t("admin.reconciliation.empty") }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <p class="reconciliation__note">
        {{
          data.remainder_household_names.length > 0
            ? t("admin.reconciliation.remainder", {
                names: data.remainder_household_names.join(", "),
              })
            : t("admin.reconciliation.noRemainder")
        }}
      </p>
    </template>

    <Skeleton v-else-if="isLoading" height="12rem" />
  </div>
</template>

<script setup lang="ts">
  import { useConfirm } from "primevue/useconfirm";
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    getPeriodReconciliation,
    putPeriodBill,
    type ReconciliationOut,
    restatePeriod,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";
  import { formatKwh, formatUah, toDecimal } from "@shared/utils/format";

  const props = defineProps<{ period: string }>();

  const { t } = useI18n();
  const confirm = useConfirm();
  const locale = navigator.language;

  const data = ref<ReconciliationOut | null>(null);
  const error = ref<string | null>(null);
  const isLoading = ref(true);
  const isSaving = ref(false);
  const correcting = ref(false);
  const billDay = ref<number | null>(null);
  const billNight = ref<number | null>(null);
  const billTotal = ref<number | null>(null);

  const isClosed = computed(() => data.value?.status === "closed");
  const canSave = computed(
    () => billDay.value !== null && billNight.value !== null && billTotal.value !== null
  );

  const variantKey = computed(() => {
    const variance = data.value?.variance_uah;

    if (variance == null) {
      return "noBill";
    }

    const value = toDecimal(variance);

    if (value === 0) {
      return "matches";
    }

    return value > 0 ? "surplus" : "shortfall";
  });

  const resultText = computed(() => {
    const current = data.value;

    if (!current) {
      return "";
    }

    if (variantKey.value === "noBill") {
      return t("admin.reconciliation.noBill");
    }

    return t(`admin.reconciliation.${variantKey.value}`, {
      amount: uah(String(Math.abs(toDecimal(current.variance_uah)))),
      total: uah(current.bill_total_uah),
    });
  });

  const lossText = computed(() => {
    const current = data.value;

    if (!current || current.loss_uah == null) {
      return t("admin.reconciliation.lossUnknown");
    }

    return t("admin.reconciliation.lossValue", {
      kwh: current.kwh_loss == null ? "—" : formatKwh(current.kwh_loss, locale, "kWh"),
      percent: current.loss_percent ?? "—",
      uah: formatUah(current.loss_uah, locale),
    });
  });

  function uah(value: string | null | undefined): string {
    return formatUah(value, locale);
  }

  function kwh(value: string | null | undefined): string {
    return formatKwh(value, locale, "kWh");
  }

  function fillBill(current: ReconciliationOut): void {
    billDay.value = current.bill_day_kwh == null ? null : toDecimal(current.bill_day_kwh);
    billNight.value = current.bill_night_kwh == null ? null : toDecimal(current.bill_night_kwh);
    billTotal.value = current.bill_total_uah == null ? null : toDecimal(current.bill_total_uah);
  }

  async function load(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      data.value = await getPeriodReconciliation(props.period);
      fillBill(data.value);
    } catch (caught: unknown) {
      error.value =
        caught instanceof ApiError && caught.message === "noRateConfigured"
          ? "errors.noRateConfigured"
          : "errors.requestFailed";
    } finally {
      isLoading.value = false;
    }
  }

  async function save(): Promise<void> {
    if (!canSave.value) {
      return;
    }

    isSaving.value = true;

    try {
      await putPeriodBill(props.period, {
        day_kwh: String(billDay.value),
        night_kwh: String(billNight.value),
        total_uah: String(billTotal.value),
      });
      await load();
    } catch (caught: unknown) {
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
    } finally {
      isSaving.value = false;
    }
  }

  function requestBillCorrection(options: { dryRun: boolean; reason: string }) {
    return restatePeriod(props.period, { bill_total_uah: String(billTotal.value) }, options);
  }

  async function onCorrectionPosted(): Promise<void> {
    correcting.value = false;
    await load();
  }

  function askToSave(): void {
    if (data.value?.bill_total_uah == null) {
      void save();
      return;
    }

    confirm.require({
      accept: () => void save(),
      acceptLabel: t("admin.reconciliation.replaceAccept"),
      header: t("admin.reconciliation.replaceTitle"),
      message: t("admin.reconciliation.replaceBody", { period: props.period }),
      rejectLabel: t("admin.reconciliation.replaceReject"),
    });
  }

  watch(() => props.period, load);
  onMounted(load);
</script>

<style scoped lang="scss">
  .reconciliation {
    @include layout.stack(var(--s-app-space-4));
    min-width: 0;

    &__result {
      border: 1px solid var(--s-content-border-color);
      border-radius: var(--s-app-radius-md);
      font-weight: 600;
      padding: var(--s-app-space-3) var(--s-app-space-4);

      &--ok {
        border-color: var(--s-green-500);
      }
    }

    &__top {
      @include layout.stack(var(--s-app-space-4));

      @include layout.respond-to("lg") {
        display: grid;
        gap: var(--s-app-space-4);
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      }
    }

    &__card,
    &__tile,
    &__table-card {
      background: var(--s-content-background);
      border: 1px solid var(--s-content-border-color);
      border-radius: var(--s-app-radius-md);
      min-width: 0;
    }

    &__card {
      @include layout.stack(var(--s-app-space-3));
      padding: var(--s-app-space-4);
    }

    &__card-title {
      font-size: 1rem;
      margin: 0;
    }

    &__field {
      @include layout.stack(var(--s-app-space-2));
      min-width: 0;
    }

    &__tiles {
      @include layout.stack(var(--s-app-space-3));
    }

    &__tile {
      @include layout.stack(var(--s-app-space-1));
      padding: var(--s-app-space-3) var(--s-app-space-4);
    }

    &__tile-label {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      font-size: 0.8rem;
    }

    &__tile-value {
      font-size: 1.1rem;
      font-weight: 600;
      overflow-wrap: anywhere;
    }

    &__scroll {
      overflow-x: auto;
    }

    &__table {
      border-collapse: collapse;
      font-size: 0.9rem;
      min-width: 44rem;
      width: 100%;

      th,
      td {
        padding: var(--s-app-space-3);
        text-align: left;
        white-space: nowrap;
      }

      tbody tr + tr {
        border-top: 1px solid var(--s-content-border-color);
      }
    }

    &__tag {
      border: 1px solid var(--s-content-border-color);
      border-radius: 999px;
      font-size: 0.7rem;
      margin-left: var(--s-app-space-2);
      padding: 0 0.5rem;
    }

    &__empty {
      text-align: center !important;
    }

    &__note {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 0.85rem;
      margin: 0;
    }
  }
</style>

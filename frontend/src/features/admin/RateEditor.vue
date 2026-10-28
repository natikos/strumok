<template>
  <div class="rate-editor">
    <Button
      class="rate-editor__toggle"
      icon="pi pi-pencil"
      severity="secondary"
      variant="text"
      :aria-expanded="isOpen"
      :aria-label="t('admin.rateEdit.edit', { period: rate.effective_from })"
      @click="isOpen = !isOpen"
    />

    <div v-if="isOpen" class="rate-editor__panel">
      <p v-if="locked" class="rate-editor__note">
        {{ t("admin.rateEdit.lockedNote", { periods: rate.used_by_closed_periods.join(", ") }) }}
      </p>

      <template v-else>
        <div class="rate-editor__field">
          <label :for="`rate-day-${rate.id}`">{{ t("admin.dayRate") }}</label>
          <InputNumber
            v-model="day"
            :input-id="`rate-day-${rate.id}`"
            :min="0"
            :min-fraction-digits="2"
            :max-fraction-digits="4"
            fluid
          />
        </div>
        <div class="rate-editor__field">
          <label :for="`rate-night-${rate.id}`">{{ t("admin.nightRate") }}</label>
          <InputNumber
            v-model="night"
            :input-id="`rate-night-${rate.id}`"
            :min="0"
            :min-fraction-digits="2"
            :max-fraction-digits="4"
            fluid
          />
        </div>
        <InputText
          v-model="reason"
          fluid
          :placeholder="t('admin.rateEdit.reason')"
          :aria-label="t('admin.rateEdit.reason')"
        />
        <div class="rate-editor__actions">
          <Button
            :disabled="isBusy || !canSave"
            :label="t('admin.rateEdit.save')"
            @click="askSave"
          />
          <Button
            :disabled="isBusy"
            severity="danger"
            variant="outlined"
            :label="t('admin.rateEdit.delete')"
            @click="askDelete"
          />
        </div>
      </template>
    </div>

    <div v-if="rate.history.length > 0" class="rate-editor__history">
      <span class="rate-editor__history-title">{{ t("admin.rateEdit.history") }}</span>
      <ul>
        <li v-for="(change, index) in rate.history" :key="index">
          {{ t(`admin.rateEdit.action${capitalize(change.action)}`) }} ·
          {{ t("admin.rateEdit.by", { when: formatWhen(change.created_at), who: change.actor_name ?? "—" }) }}
          <template v-if="change.before && change.after">
            · {{ change.before["day_rate_uah"] }}/{{ change.before["night_rate_uah"] }} →
            {{ change.after["day_rate_uah"] }}/{{ change.after["night_rate_uah"] }}
          </template>
          <template v-if="change.reason"> · {{ change.reason }}</template>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { useConfirm } from "primevue/useconfirm";
  import { computed, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { ApiError } from "@shared/api/client";
  import {
    deleteElectricityRate,
    type ElectricityRateOut,
    updateElectricityRate,
  } from "@shared/api/electricity-rates";
  import { toDecimal } from "@shared/utils/format";

  const props = defineProps<{ rate: ElectricityRateOut }>();
  const emit = defineEmits<{ changed: [] }>();

  const { t } = useI18n();
  const confirm = useConfirm();

  const isOpen = ref(false);
  const isBusy = ref(false);
  const day = ref<number | null>(toDecimal(props.rate.day_rate_uah));
  const night = ref<number | null>(toDecimal(props.rate.night_rate_uah));
  const reason = ref("");

  const locked = computed(() => props.rate.used_by_closed_periods.length > 0);
  const canSave = computed(
    () =>
      day.value !== null &&
      night.value !== null &&
      day.value > 0 &&
      night.value > 0 &&
      (day.value !== toDecimal(props.rate.day_rate_uah) ||
        night.value !== toDecimal(props.rate.night_rate_uah))
  );

  function capitalize(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function formatWhen(value: string): string {
    return new Date(value).toLocaleString();
  }

  async function run(action: () => Promise<unknown>): Promise<void> {
    isBusy.value = true;

    try {
      await action();
      isOpen.value = false;
      reason.value = "";
      emit("changed");
    } catch (error: unknown) {
      if (!(error instanceof ApiError)) {
        throw error;
      }
      emit("changed");
    } finally {
      isBusy.value = false;
    }
  }

  function askSave(): void {
    confirm.require({
      accept: () =>
        void run(() =>
          updateElectricityRate(props.rate.id, {
            day_rate_uah: String(day.value),
            night_rate_uah: String(night.value),
            ...(reason.value ? { reason: reason.value } : {}),
          })
        ),
      acceptLabel: t("admin.rateEdit.confirm"),
      header: t("admin.rateEdit.saveTitle", { period: props.rate.effective_from }),
      message: t("admin.rateEdit.saveBody"),
      rejectLabel: t("admin.rateEdit.cancel"),
    });
  }

  function askDelete(): void {
    confirm.require({
      accept: () =>
        void run(() => deleteElectricityRate(props.rate.id, reason.value || undefined)),
      acceptLabel: t("admin.rateEdit.confirm"),
      header: t("admin.rateEdit.deleteTitle", { period: props.rate.effective_from }),
      message: t("admin.rateEdit.deleteBody"),
      rejectLabel: t("admin.rateEdit.cancel"),
    });
  }
</script>

<style scoped lang="scss">
  .rate-editor {
    @include layout.stack(var(--s-app-space-2));
    min-width: 0;

    &__toggle {
      align-self: flex-start;
      min-height: 44px;
      min-width: 44px;
    }

    &__panel {
      @include layout.stack(var(--s-app-space-3));
    }

    &__field {
      @include layout.stack(var(--s-app-space-1));
      min-width: 0;
    }

    &__actions {
      @include layout.row(var(--s-app-space-2), center);
      flex-wrap: wrap;
    }

    &__note,
    &__history {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 0.8rem;
      margin: 0;
    }

    &__history ul {
      margin: var(--s-app-space-1) 0 0;
      padding-left: var(--s-app-space-4);
    }

    &__history-title {
      font-weight: 600;
    }
  }
</style>

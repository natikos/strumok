<template>
  <div class="meter-change">
    <h3 class="meter-change__title">
      {{ t("admin.meterChange.title", { name: household.name, period }) }}
    </h3>

    <fieldset class="meter-change__group">
      <legend class="meter-change__legend">{{ t("admin.meterChange.oldMeter") }}</legend>
      <div class="meter-change__fields">
        <div class="meter-change__field">
          <label :for="`mc-old-day-${household.id}`">{{ t("admin.readingEdit.day") }}</label>
          <InputNumber v-model="oldDay" :input-id="`mc-old-day-${household.id}`" :min="0" :min-fraction-digits="2" :max-fraction-digits="2" fluid />
        </div>
        <div class="meter-change__field">
          <label :for="`mc-old-night-${household.id}`">{{ t("admin.readingEdit.night") }}</label>
          <InputNumber v-model="oldNight" :input-id="`mc-old-night-${household.id}`" :min="0" :min-fraction-digits="2" :max-fraction-digits="2" fluid />
        </div>
      </div>
    </fieldset>

    <fieldset class="meter-change__group">
      <legend class="meter-change__legend">{{ t("admin.meterChange.newMeter") }}</legend>
      <div class="meter-change__fields">
        <div class="meter-change__field">
          <label :for="`mc-new-day-${household.id}`">{{ t("admin.readingEdit.day") }}</label>
          <InputNumber v-model="newDay" :input-id="`mc-new-day-${household.id}`" :min="0" :min-fraction-digits="2" :max-fraction-digits="2" fluid />
        </div>
        <div class="meter-change__field">
          <label :for="`mc-new-night-${household.id}`">{{ t("admin.readingEdit.night") }}</label>
          <InputNumber v-model="newNight" :input-id="`mc-new-night-${household.id}`" :min="0" :min-fraction-digits="2" :max-fraction-digits="2" fluid />
        </div>
      </div>
    </fieldset>

    <InputText v-model="reason" fluid :maxlength="500" :placeholder="t('admin.readingEdit.reason')" :aria-label="t('admin.readingEdit.reason')" />
    <p v-if="!canSubmit" class="meter-change__hint">{{ t("admin.meterChange.hint") }}</p>
    <p v-if="error" role="alert" class="meter-change__error">{{ t(`errors.${error}`, t("admin.meterChange.failed")) }}</p>

    <div class="meter-change__actions">
      <Button :disabled="!canSubmit || isBusy" :loading="isBusy" :label="t('admin.meterChange.submit')" @click="askToRecord" />
      <Button severity="secondary" variant="text" :label="t('admin.readingEdit.reject')" @click="$emit('cancel')" />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { useConfirm } from "primevue/useconfirm";
  import { useToast } from "primevue/usetoast";
  import { computed, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { recordMeterChange } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";
  import { toDecimal } from "@shared/utils/format";

  const props = defineProps<{
    household: { id: number; name: string };
    period: string;
  }>();
  const emit = defineEmits<{ cancel: []; changed: [] }>();

  const { t } = useI18n();
  const confirm = useConfirm();
  const toast = useToast();

  const oldDay = ref<number | null>(null);
  const oldNight = ref<number | null>(null);
  const newDay = ref<number | null>(null);
  const newNight = ref<number | null>(null);
  const reason = ref("");
  const isBusy = ref(false);
  const error = ref<string | null>(null);

  const canSubmit = computed(
    () =>
      reason.value.trim().length > 0 &&
      [oldDay, oldNight, newDay, newNight].every((field) => field.value !== null)
  );

  async function record(): Promise<void> {
    isBusy.value = true;
    error.value = null;

    try {
      const result = await recordMeterChange(props.household.id, {
        new_start_day: String(newDay.value),
        new_start_night: String(newNight.value),
        old_final_day: String(oldDay.value),
        old_final_night: String(oldNight.value),
        period: props.period,
        reason: reason.value.trim(),
      });
      const usage =
        result.day_usage_kwh !== null && result.night_usage_kwh !== null
          ? t("admin.meterChange.usage", {
              day: toDecimal(result.day_usage_kwh),
              night: toDecimal(result.night_usage_kwh),
            })
          : t("admin.meterChange.usagePending");
      toast.add({
        life: 6000,
        severity: "success",
        summary: t("admin.meterChange.recorded", { name: props.household.name }),
        detail: usage,
      });
      emit("changed");
    } catch (caught: unknown) {
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
      error.value = caught.message;
    } finally {
      isBusy.value = false;
    }
  }

  function askToRecord(): void {
    confirm.require({
      accept: () => void record(),
      acceptLabel: t("admin.readingEdit.accept"),
      header: t("admin.meterChange.confirmTitle", { name: props.household.name }),
      message: t("admin.meterChange.confirmBody", {
        newDay: newDay.value,
        newNight: newNight.value,
        oldDay: oldDay.value,
        oldNight: oldNight.value,
        reason: reason.value.trim(),
      }),
      rejectLabel: t("admin.readingEdit.reject"),
    });
  }
</script>

<style scoped lang="scss">
  .meter-change {
    @include layout.stack(var(--s-app-space-3));
    min-width: 0;
    white-space: normal;

    &__title {
      font-size: 0.95rem;
      margin: 0;
    }

    &__group {
      @include layout.stack(var(--s-app-space-2));
      border: 0;
      margin: 0;
      min-width: 0;
      padding: 0;
    }

    &__legend {
      font-size: 0.85rem;
      font-weight: 500;
      padding: 0;
    }

    &__fields {
      @include layout.stack(var(--s-app-space-3));

      @include layout.respond-to("sm") {
        display: grid;
        gap: var(--s-app-space-3);
        grid-template-columns: 1fr 1fr;
      }
    }

    &__field {
      @include layout.stack(var(--s-app-space-1));
      min-width: 0;
    }

    &__hint {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 0.8rem;
      margin: 0;
    }

    &__error {
      color: var(--s-red-500);
      font-size: 0.8rem;
      margin: 0;
    }

    &__actions {
      @include layout.row(var(--s-app-space-2), center);
      flex-wrap: wrap;
    }
  }
</style>

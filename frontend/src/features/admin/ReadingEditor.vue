<template>
  <div class="reading-editor">
    <RestatementPreview
      v-if="restating"
      :request="requestRestatement"
      @cancel="restating = false"
      @posted="onDone"
    />

    <MeterChangeForm
      v-else-if="replacingMeter"
      :household="household"
      :period="period"
      @cancel="replacingMeter = false"
      @changed="onDone"
    />

    <template v-else>
      <h3 class="reading-editor__title">
        {{ reading ? t("admin.readingEdit.correct", { name: household.name }) : t("admin.readingEdit.submitFor", { name: household.name }) }}
      </h3>
      <div class="reading-editor__fields">
        <div class="reading-editor__field">
          <label :for="`edit-day-${household.id}`">{{ t("admin.readingEdit.day") }}</label>
          <InputNumber v-model="day" :input-id="`edit-day-${household.id}`" :min="0" :min-fraction-digits="2" :max-fraction-digits="2" fluid />
        </div>
        <div class="reading-editor__field">
          <label :for="`edit-night-${household.id}`">{{ t("admin.readingEdit.night") }}</label>
          <InputNumber v-model="night" :input-id="`edit-night-${household.id}`" :min="0" :min-fraction-digits="2" :max-fraction-digits="2" fluid />
        </div>
      </div>
      <InputText v-model="reason" fluid :maxlength="500" :placeholder="t('admin.readingEdit.reason')" :aria-label="t('admin.readingEdit.reason')" />
      <p v-if="!reasonFilled" class="reading-editor__hint">{{ t("admin.readingEdit.reasonHint") }}</p>
      <div class="reading-editor__actions">
        <Button
          :disabled="!canSubmit || isBusy"
          :aria-disabled="!canSubmit || isBusy"
          :label="reading ? t('admin.readingEdit.save') : t('admin.readingEdit.submit')"
          @click="askToApply"
        />
        <Button
          v-if="reading"
          :disabled="!reasonFilled || isBusy"
          severity="danger"
          variant="outlined"
          :label="t('admin.readingEdit.void')"
          @click="askToVoid"
        />
        <Button
          severity="secondary"
          variant="outlined"
          :disabled="isBusy"
          :label="t('admin.meterChange.open')"
          @click="replacingMeter = true"
        />
        <Button severity="secondary" variant="text" :label="t('admin.readingEdit.close')" @click="$emit('close')" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { useConfirm } from "primevue/useconfirm";
  import { computed, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    type AdminReadingOut,
    correctAdminReading,
    restatePeriod,
    submitReadingOnBehalf,
    voidAdminReading,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";
  import { toDecimal } from "@shared/utils/format";

  const props = defineProps<{
    household: { id: number; name: string };
    period: string;
    reading: AdminReadingOut | null;
  }>();
  const emit = defineEmits<{ changed: []; close: [] }>();

  const { t } = useI18n();
  const confirm = useConfirm();

  const day = ref<number | null>(props.reading ? toDecimal(props.reading.day_meter_value) : null);
  const night = ref<number | null>(props.reading ? toDecimal(props.reading.night_meter_value) : null);
  const reason = ref("");
  const isBusy = ref(false);
  const restating = ref(false);
  const replacingMeter = ref(false);

  const reasonFilled = computed(() => reason.value.trim().length > 0);
  const canSubmit = computed(() => reasonFilled.value && day.value !== null && night.value !== null);

  function payload() {
    return {
      day_meter_value: String(day.value),
      night_meter_value: String(night.value),
      reason: reason.value.trim(),
    };
  }

  function requestRestatement(options: { dryRun: boolean; reason: string }) {
    return restatePeriod(
      props.period,
      {
        readings: [
          {
            day_meter_value: String(day.value),
            household_id: props.household.id,
            night_meter_value: String(night.value),
          },
        ],
      },
      { dryRun: options.dryRun, reason: options.reason || reason.value.trim() }
    );
  }

  function onDone(): void {
    restating.value = false;
    emit("changed");
    emit("close");
  }

  async function run(action: () => Promise<void>): Promise<void> {
    isBusy.value = true;

    try {
      await action();
      emit("changed");
      emit("close");
    } catch (error: unknown) {
      if (!(error instanceof ApiError)) {
        throw error;
      }
      // A closed period can't be edited directly: the same change becomes a restatement.
      if (error.message === "periodClosed") {
        restating.value = true;
      }
    } finally {
      isBusy.value = false;
    }
  }

  function askToApply(): void {
    const before = props.reading;

    confirm.require({
      accept: () =>
        void run(() =>
          before
            ? correctAdminReading(before.id, payload())
            : submitReadingOnBehalf(props.household.id, { ...payload(), period: props.period })
        ),
      acceptLabel: t("admin.readingEdit.accept"),
      header: t("admin.readingEdit.diffTitle", { name: props.household.name }),
      message: `${t("admin.readingEdit.diff", {
        dayAfter: day.value,
        dayBefore: before ? toDecimal(before.day_meter_value) : "—",
        nightAfter: night.value,
        nightBefore: before ? toDecimal(before.night_meter_value) : "—",
      })}. ${reason.value.trim()}`,
      rejectLabel: t("admin.readingEdit.reject"),
    });
  }

  function askToVoid(): void {
    const before = props.reading;

    if (!before) {
      return;
    }

    confirm.require({
      accept: () => void run(() => voidAdminReading(before.id, reason.value.trim())),
      acceptLabel: t("admin.readingEdit.accept"),
      header: t("admin.readingEdit.voidTitle", { name: props.household.name }),
      message: t("admin.readingEdit.voidBody", { reason: reason.value.trim() }),
      rejectLabel: t("admin.readingEdit.reject"),
    });
  }
</script>

<style scoped lang="scss">
  .reading-editor {
    @include layout.stack(var(--s-app-space-3));
    min-width: 0;
    white-space: normal;

    &__title {
      font-size: 0.95rem;
      margin: 0;
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

    &__actions {
      @include layout.row(var(--s-app-space-2), center);
      flex-wrap: wrap;
    }
  }
</style>

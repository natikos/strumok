<template>
  <div class="restatement">
    <Skeleton v-if="isLoading" height="6rem" />

    <template v-else-if="preview">
      <p class="restatement__summary">
        {{
          t("admin.restatement.summary", {
            households: householdCount,
            periods: preview.affected_periods.length,
          })
        }}
      </p>
      <p v-if="preview.is_zero_sum" class="restatement__note">
        {{ t("admin.restatement.zeroSum") }}
      </p>
      <p v-if="preview.lines.length === 0" class="restatement__note">
        {{ t("admin.restatement.noChange") }}
      </p>

      <ul class="restatement__list">
        <li v-for="line in preview.lines" :key="`${line.period}-${line.household_id}`" class="restatement__card">
          <span class="restatement__name">{{ line.household_name }} · {{ line.period }}</span>
          <span class="restatement__change">
            {{ money(line.before_uah) }} → {{ money(line.after_uah) }}
          </span>
          <span class="restatement__delta">
            {{ signed(line.delta_uah) }}
            ({{ toDecimal(line.delta_uah) < 0 ? t("admin.restatement.refund") : t("admin.restatement.extra") }})
          </span>
        </li>
      </ul>

      <label class="restatement__label" for="restatement-reason">
        {{ t("admin.restatement.reason") }}
      </label>
      <InputText id="restatement-reason" v-model="reason" fluid :maxlength="500" />
      <p v-if="!reasonFilled" class="restatement__hint">{{ t("admin.restatement.reasonHint") }}</p>

      <div class="restatement__actions">
        <Button
          :disabled="!reasonFilled || isPosting"
          :aria-disabled="!reasonFilled || isPosting"
          :loading="isPosting"
          :label="t('admin.restatement.confirm')"
          @click="post"
        />
        <Button
          severity="secondary"
          variant="text"
          :label="t('admin.restatement.cancel')"
          @click="$emit('cancel')"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import type { RestatementOut } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";
  import { formatUah, toDecimal } from "@shared/utils/format";

  const props = defineProps<{
    /** Previews with `dryRun: true`; posts with `dryRun: false` and the reason. */
    request: (options: { dryRun: boolean; reason: string }) => Promise<RestatementOut>;
  }>();
  const emit = defineEmits<{ cancel: []; posted: [] }>();

  const { t } = useI18n();
  const locale = navigator.language;

  const preview = ref<RestatementOut | null>(null);
  const reason = ref("");
  const isLoading = ref(true);
  const isPosting = ref(false);

  const reasonFilled = computed(() => reason.value.trim().length > 0);
  const householdCount = computed(
    () => new Set(preview.value?.lines.map((line) => line.household_id)).size
  );

  function money(value: string): string {
    return formatUah(value, locale);
  }

  function signed(value: string): string {
    const amount = toDecimal(value);
    return `${amount > 0 ? "+" : ""}${formatUah(value, locale)}`;
  }

  async function post(): Promise<void> {
    isPosting.value = true;

    try {
      await props.request({ dryRun: false, reason: reason.value.trim() });
      emit("posted");
    } catch (error: unknown) {
      if (!(error instanceof ApiError)) {
        throw error;
      }
    } finally {
      isPosting.value = false;
    }
  }

  onMounted(async () => {
    try {
      preview.value = await props.request({ dryRun: true, reason: "" });
    } catch (error: unknown) {
      if (!(error instanceof ApiError)) {
        throw error;
      }
      emit("cancel");
    } finally {
      isLoading.value = false;
    }
  });
</script>

<style scoped lang="scss">
  .restatement {
    @include layout.stack(var(--s-app-space-3));
    min-width: 0;

    &__summary {
      font-weight: 600;
      margin: 0;
    }

    &__note,
    &__hint {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 0.85rem;
      margin: 0;
    }

    &__list {
      @include layout.stack(var(--s-app-space-2));
      list-style: none;
      margin: 0;
      padding: 0;
    }

    &__card {
      @include layout.stack(var(--s-app-space-1));
      border: 1px solid var(--s-content-border-color);
      border-radius: var(--s-app-radius-md);
      min-width: 0;
      padding: var(--s-app-space-3);
    }

    &__name {
      font-weight: 600;
    }

    &__label {
      font-size: 0.85rem;
      font-weight: 500;
    }

    &__actions {
      @include layout.row(var(--s-app-space-2), center);
      flex-wrap: wrap;
    }
  }
</style>

<template>
  <div v-if="overview" class="period-close admin-card admin-card--padded">
    <div class="period-close__head">
      <span class="period-close__label">{{ period }}</span>
      <span class="period-close__pill" :class="`period-close__pill--${overview.status}`">
        {{ t(`admin.period.${overview.status}`) }}
      </span>
    </div>

    <p v-if="overview.status === 'closed'" class="period-close__note">
      {{ closedLine }}
    </p>

    <p v-if="unownedEstimated.length > 0" class="period-close__note period-close__note--blocked">
      {{ t("admin.period.unownedEstimated", { names: unownedEstimated.map((h) => h.name).join(", ") }) }}
    </p>

    <template v-if="overview.status === 'open'">
      <Button
        class="period-close__button"
        severity="danger"
        variant="outlined"
        :disabled="hardBlockers.length > 0 || (needsAcknowledgement && !acknowledged) || isClosing"
        :loading="isClosing"
        :label="t('admin.period.close', { period })"
        @click="askToClose"
      />
      <label v-if="needsAcknowledgement" class="period-close__ack">
        <input v-model="acknowledged" type="checkbox" />
        {{ t("admin.period.acknowledge", { count: overview.unreviewed_count }) }}
      </label>
      <p
        v-for="blocker in hardBlockers"
        :key="blocker"
        class="period-close__note period-close__note--blocked"
      >
        {{ t(`admin.period.blockers.${blocker}`, { period }) }}
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { format } from "date-fns";
  import { useConfirm } from "primevue/useconfirm";
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    closeAdminPeriod,
    listAdminPeriods,
    type PeriodCloseOut,
    type PeriodOverviewOut,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";

  const props = defineProps<{ period: string }>();
  const emit = defineEmits<{ closed: [] }>();

  const { t } = useI18n();
  const confirm = useConfirm();

  const overview = ref<PeriodOverviewOut | null>(null);
  const isClosing = ref(false);

  const acknowledged = ref(false);
  const unownedEstimated = ref<PeriodCloseOut["unowned_estimated"]>([]);

  // Unreviewed readings are a soft blocker: the head may close anyway.
  const hardBlockers = computed(
    () => overview.value?.blockers.filter((b) => b !== "periodHasUnreviewedReadings") ?? []
  );
  const needsAcknowledgement = computed(() => (overview.value?.unreviewed_count ?? 0) > 0);

  const closedLine = computed(() => {
    const current = overview.value;

    if (!current?.closed_at) {
      return "";
    }

    const date = format(new Date(current.closed_at), "yyyy-MM-dd");

    return current.closed_by_name
      ? t("admin.period.closedOn", { date, name: current.closed_by_name })
      : t("admin.period.closedOnly", { date });
  });

  async function load(): Promise<void> {
    const periods = await listAdminPeriods();
    overview.value = periods.find((item) => item.period === props.period) ?? null;
  }

  function askToClose(): void {
    const current = overview.value;

    if (!current) {
      return;
    }

    confirm.require({
      accept: () => void close(),
      acceptLabel: t("admin.period.confirmAccept"),
      header: t("admin.period.confirmTitle", { period: props.period }),
      message: t("admin.period.confirmBody", {
        charged: current.readings_count,
        missing: current.missing_count,
        period: props.period,
      }),
      rejectLabel: t("admin.period.confirmReject"),
    });
  }

  async function close(): Promise<void> {
    isClosing.value = true;

    try {
      const closed = await closeAdminPeriod(props.period, acknowledged.value);
      overview.value = closed;
      unownedEstimated.value = closed.unowned_estimated ?? [];
      emit("closed");
    } catch (error: unknown) {
      if (!(error instanceof ApiError)) {
        throw error;
      }
      await load();
    } finally {
      isClosing.value = false;
    }
  }

  watch(() => props.period, () => {
    unownedEstimated.value = [];
    void load();
  });
  onMounted(load);
</script>

<style scoped lang="scss">
  .period-close {
    @include layout.stack(var(--s-app-space-3));
    min-width: 0;

    &__head {
      @include layout.row(var(--s-app-space-3), center, space-between);
    }

    &__label {
      font-weight: 600;
    }

    &__pill {
      border: 1px solid var(--s-content-border-color);
      border-radius: 999px;
      font-size: 0.75rem;
      padding: 0.1rem 0.6rem;
    }

    &__button {
      min-height: 44px;
      width: 100%;

      @include layout.respond-to("lg") {
        align-self: flex-end;
        width: auto;
      }
    }

    &__ack {
      @include layout.row(var(--s-app-space-2), center);
      font-size: 0.85rem;
    }

    &__note {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 0.85rem;
      margin: 0;

      &--blocked {
        color: var(--s-amber-500);
      }
    }
  }
</style>

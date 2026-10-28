<template>
  <div class="audit-log">
    <div class="audit-log__filters">
      <Select
        v-model="householdId"
        class="audit-log__filter"
        :options="households"
        option-label="name"
        option-value="id"
        show-clear
        :placeholder="t('admin.audit.allHouseholds')"
        :aria-label="t('admin.audit.household')"
      />
      <InputText
        v-model="period"
        class="audit-log__filter"
        inputmode="numeric"
        maxlength="7"
        :placeholder="t('admin.audit.period')"
        :aria-label="t('admin.audit.period')"
      />
      <Select
        v-model="action"
        class="audit-log__filter"
        :options="ACTIONS"
        show-clear
        :placeholder="t('admin.audit.allActions')"
        :aria-label="t('admin.audit.action')"
      >
        <template #option="{ option }">{{ actionLabel(option) }}</template>
        <template #value="{ value, placeholder }">
          {{ value ? actionLabel(value) : placeholder }}
        </template>
      </Select>
    </div>

    <ErrorState v-if="error" :message-key="error" @retry="load(true)" />

    <p v-else-if="!isLoading && entries.length === 0" class="audit-log__empty">
      {{ t("admin.audit.empty") }}
    </p>

    <ul class="audit-log__list">
      <li v-for="entry in entries" :key="entry.id" class="audit-entry">
        <div class="audit-entry__head">
          <span class="audit-entry__action">{{ actionLabel(entry.action) }}</span>
          <time class="audit-entry__time" :datetime="entry.created_at">{{
            formatTime(entry.created_at)
          }}</time>
        </div>
        <div class="audit-entry__meta">
          {{
            t("admin.audit.by", {
              name: entry.actor
                ? `${entry.actor.first_name} ${entry.actor.last_name}`
                : t("admin.audit.system"),
            })
          }}
          <template v-if="entry.period"> · {{ entry.period }}</template>
        </div>
        <div v-if="entry.before || entry.after" class="audit-entry__diff">
          {{ summarize(entry.before) }} → {{ summarize(entry.after) }}
        </div>
        <div v-if="entry.reason" class="audit-entry__reason">
          {{ t("admin.audit.reason", { reason: entry.reason }) }}
        </div>
      </li>
    </ul>

    <Button
      v-if="nextCursor !== null"
      class="audit-log__more"
      severity="secondary"
      :label="t('admin.audit.loadMore')"
      :loading="isLoading"
      @click="load(false)"
    />
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    type AdminHouseholdOut,
    type AuditLogEntryOut,
    getAuditLog,
    listAdminHouseholds,
  } from "@shared/api/admin";

  const ACTIONS = ["householdCreated", "householdOwnerAssigned", "rateCreated"];
  const PERIOD_PATTERN = /^\d{4}-\d{2}$/;

  const i18n = useI18n();
  const { t } = i18n;

  const households = ref<AdminHouseholdOut[]>([]);
  const entries = ref<AuditLogEntryOut[]>([]);
  const nextCursor = ref<number | null>(null);
  const householdId = ref<number | null>(null);
  const period = ref("");
  const action = ref<string | null>(null);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  function actionLabel(value: string): string {
    return i18n.te(`admin.audit.actions.${value}`) ? t(`admin.audit.actions.${value}`) : value;
  }

  function formatTime(value: string): string {
    return new Date(value).toLocaleString();
  }

  function summarize(value: Record<string, unknown> | null | undefined): string {
    if (!value) {
      return "—";
    }

    return Object.entries(value)
      .map(([key, item]) => `${key}: ${typeof item === "string" ? item : JSON.stringify(item ?? "—")}`)
      .join(", ");
  }

  async function load(reset: boolean): Promise<void> {
    if (period.value && !PERIOD_PATTERN.test(period.value)) {
      return;
    }

    isLoading.value = true;
    error.value = null;

    try {
      const page = await getAuditLog({
        ...(action.value ? { action: action.value } : {}),
        ...(!reset && nextCursor.value !== null ? { cursor: nextCursor.value } : {}),
        ...(householdId.value !== null ? { household_id: householdId.value } : {}),
        ...(period.value ? { period: period.value } : {}),
      });
      entries.value = reset ? page.items : [...entries.value, ...page.items];
      nextCursor.value = page.next_cursor;
    } catch {
      error.value = "errors.requestFailed";
    } finally {
      isLoading.value = false;
    }
  }

  watch([householdId, period, action], () => load(true));

  onMounted(async () => {
    households.value = await listAdminHouseholds();
    await load(true);
  });
</script>

<style scoped lang="scss">
  .audit-log {
    @include layout.stack(var(--s-app-space-4));
    min-width: 0;

    &__filters {
      @include layout.stack(var(--s-app-space-2));

      @include layout.respond-to("sm") {
        display: grid;
        gap: var(--s-app-space-2);
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
    }

    &__filter {
      min-width: 0;
      width: 100%;
    }

    &__empty {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      margin: 0;
    }

    &__list {
      @include layout.stack(var(--s-app-space-3));
      list-style: none;
      margin: 0;
      padding: 0;
    }
  }

  .audit-entry {
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    min-width: 0;
    padding: var(--s-app-space-4);

    &__head {
      @include layout.row(var(--s-app-space-2), baseline, space-between);
      flex-wrap: wrap;
    }

    &__action {
      font-weight: 600;
    }

    &__time,
    &__meta,
    &__reason {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      font-size: 0.8rem;
    }

    &__diff {
      font-size: 0.85rem;
      margin-top: var(--s-app-space-2);
      overflow-wrap: anywhere;
    }
  }
</style>

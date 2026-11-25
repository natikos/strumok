<template>
  <section class="outcome" :aria-label="t('admin.bank.outcome.title')">
    <h3 class="outcome__title">{{ t("admin.bank.outcome.title") }}</h3>

    <ErrorState v-if="error" :message-key="error" @retry="loadFiles" />

    <p v-else-if="!isLoading && !files.length" class="outcome__empty">
      {{ t("admin.bank.outcome.empty") }}
    </p>

    <template v-else-if="files.length">
      <label class="outcome__picker">
        <span>{{ t("admin.bank.outcome.file") }}</span>
        <Select
          v-model="selectedId"
          :options="fileOptions"
          option-label="label"
          option-value="id"
          fluid
          @update:model-value="loadOutcome"
        />
      </label>

      <template v-if="outcome">
        <p class="outcome__meta">
          {{ t("admin.bank.outcome.handled", { count: outcome.handled_count }) }}
          · {{ t("admin.bank.outcome.duplicates", { count: outcome.file.credits_duplicate }) }}
        </p>
        <p v-if="!total && !outcome.handled_count" class="outcome__empty">
          {{ t("admin.bank.outcome.noCredits") }}
        </p>

        <section
          v-for="group in groups"
          :key="group.key"
          class="outcome__group"
          :class="`outcome__group--${group.key}`"
        >
          <h4 class="outcome__group-title">
            {{ t(`admin.bank.outcome.${group.key}`) }} ({{ group.rows.length }})
          </h4>
          <ul v-if="group.rows.length" class="outcome__list">
            <li v-for="row in group.rows" :key="row.id" class="outcome__row">
              <div class="outcome__line">
                <span class="outcome__date">{{ row.operation_date }}</span>
                <strong class="outcome__amount">{{ money(row.amount_uah) }}</strong>
              </div>
              <p class="outcome__payer">{{ row.payer_name || "—" }}</p>
              <p class="outcome__purpose">{{ row.purpose }}</p>
              <p v-if="row.households.length" class="outcome__match">
                {{ t(row.matchKey, { name: row.households.join(", ") }) }}
              </p>
            </li>
          </ul>
        </section>
        <p v-if="outcome.needs_attention.length || outcome.unmatched.length" class="outcome__meta">
          {{ t("admin.bank.outcome.actHint") }}
        </p>
      </template>
    </template>
  </section>
</template>

<script setup lang="ts">
  import { format } from "date-fns";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    type AdminHouseholdOut,
    getStatementOutcome,
    listAdminHouseholds,
    listStatementFiles,
    type StatementFileOut,
    type StatementOutcomeOut,
  } from "@shared/api/admin";
  import { APP_LOCALE, formatUah } from "@shared/utils/format";

  interface Row {
    id: number;
    operation_date: string;
    amount_uah: string;
    payer_name: string;
    purpose: string;
    households: string[];
    matchKey: string;
  }

  const { t } = useI18n();

  const files = ref<StatementFileOut[]>([]);
  const households = ref<AdminHouseholdOut[]>([]);
  const outcome = ref<StatementOutcomeOut | null>(null);
  const selectedId = ref<number | null>(null);
  const error = ref<string | null>(null);
  const isLoading = ref(true);

  const fileOptions = computed(() =>
    files.value.map((file) => ({
      id: file.id,
      label: t("admin.bank.outcome.fileOption", {
        name: file.original_filename,
        date: format(new Date(file.uploaded_at), "dd.MM HH:mm"),
      }),
    })),
  );

  function money(value: string): string {
    return formatUah(value, APP_LOCALE);
  }

  function householdName(id: number): string {
    return households.value.find((household) => household.id === id)?.name ?? String(id);
  }

  const groups = computed(() => {
    const current = outcome.value;

    if (!current) {
      return [];
    }

    const suggested = (rows: StatementOutcomeOut["needs_attention"]): Row[] =>
      rows.map((row) => ({
        ...row,
        households: row.suggestions.map((s) => householdName(s.household_id)),
        matchKey: "admin.bank.outcome.suggestedFor",
      }));

    return [
      {
        key: "auto",
        rows: current.auto_confirmed.map(
          (row): Row => ({
            ...row,
            households: row.payments.map((p) => householdName(p.household_id)),
            matchKey: "admin.bank.outcome.paidFor",
          }),
        ),
      },
      { key: "attention", rows: suggested(current.needs_attention) },
      { key: "unmatched", rows: suggested(current.unmatched) },
    ];
  });

  const total = computed(() => groups.value.reduce((sum, group) => sum + group.rows.length, 0));

  async function loadOutcome(id: number | null): Promise<void> {
    if (id === null) {
      return;
    }

    error.value = null;

    try {
      outcome.value = await getStatementOutcome(id);
    } catch {
      error.value = "errors.requestFailed";
    }
  }

  async function loadFiles(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      [files.value, households.value] = await Promise.all([
        listStatementFiles(),
        listAdminHouseholds(),
      ]);
      selectedId.value = files.value[0]?.id ?? null;
      await loadOutcome(selectedId.value);
    } catch {
      error.value = "errors.requestFailed";
    } finally {
      isLoading.value = false;
    }
  }

  onMounted(loadFiles);
</script>

<style scoped lang="scss">
  .outcome {
    display: grid;
    gap: var(--s-app-space-2);
    min-width: 0;

    &__title,
    &__group-title,
    &__empty,
    &__meta {
      margin: 0;
    }

    &__title {
      font-size: 1rem;
    }

    &__group-title {
      font-size: 0.9375rem;
    }

    &__meta {
      opacity: 0.75;
      font-size: 0.875rem;
    }

    &__picker {
      display: grid;
      gap: var(--s-app-space-1);
      min-width: 0;
    }

    &__group {
      display: grid;
      gap: var(--s-app-space-1);
      min-width: 0;
    }

    &__list {
      display: grid;
      gap: var(--s-app-space-1);
      list-style: none;
      margin: 0;
      padding: 0;
    }

    &__row {
      border: 1px solid var(--s-content-border-color);
      border-radius: var(--s-app-radius-md);
      display: grid;
      gap: 2px;
      min-width: 0;
      padding: var(--s-app-space-2);
    }

    &__group--auto &__row {
      border-left: 4px solid var(--s-green-500);
    }

    &__group--attention &__row {
      border-left: 4px solid var(--s-amber-500);
    }

    &__group--unmatched &__row {
      border-left: 4px solid var(--s-red-500);
    }

    &__line {
      align-items: baseline;
      display: flex;
      gap: var(--s-app-space-2);
      justify-content: space-between;
    }

    &__payer,
    &__purpose,
    &__match {
      margin: 0;
      overflow-wrap: anywhere;
    }

    &__purpose,
    &__match {
      font-size: 0.875rem;
    }
  }
</style>

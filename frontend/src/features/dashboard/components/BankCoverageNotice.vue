<template>
  <p v-if="coverage" class="bank-coverage" role="status">
    <InfoCircle class="bank-coverage__icon" aria-hidden="true" />
    <span class="bank-coverage__text">
      <template v-if="coverage.awaiting_statement || !coveredLabel">
        {{ t("bankCoverage.awaiting") }}
      </template>
      <template v-else>{{ t("bankCoverage.includedUpTo", { date: coveredLabel }) }}</template>
      <span v-if="coverage.last_imported_at" class="bank-coverage__import">
        {{ t("bankCoverage.lastImported", { date: formatKyivDate(coverage.last_imported_at, locale) }) }}
      </span>
    </span>
  </p>
</template>

<script setup lang="ts">
  import { InfoCircle } from "@primeicons/vue";
  import { format, parseISO } from "date-fns";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { type BankCoverageOut, getBankCoverage } from "@shared/api/billing";
  import { APP_LOCALE, formatKyivDate } from "@shared/utils/format";

  const { t } = useI18n();
  const locale = APP_LOCALE;

  const coverage = ref<BankCoverageOut | null>(null);
  const coveredLabel = computed(() =>
    coverage.value?.covered_through ? format(parseISO(coverage.value.covered_through), "dd.MM") : ""
  );

  // The notice is advisory: if coverage can't load, show nothing rather than guess.
  onMounted(async () => {
    try {
      coverage.value = await getBankCoverage();
    } catch {
      coverage.value = null;
    }
  });
</script>

<style scoped lang="scss">
  .bank-coverage {
    align-items: flex-start;
    color: color-mix(in srgb, var(--s-content-color), transparent 30%);
    display: flex;
    font-size: 0.85rem;
    gap: var(--s-app-space-2);
    margin: 0;
    min-width: 0;

    &__icon {
      flex: none;
      margin-top: 0.15em;
    }

    &__text {
      min-width: 0;
    }

    &__import {
      display: block;
    }
  }
</style>

<template>
  <p
    v-if="coverage"
    class="bank-coverage"
    :class="{ 'bank-coverage--awaiting': coverage.awaiting_statement }"
    role="status"
  >
    <template v-if="coverage.awaiting_statement || !coveredLabel">
      {{ t("bankCoverage.awaiting") }}
    </template>
    <template v-else>{{ t("bankCoverage.includedUpTo", { date: coveredLabel }) }}</template>
    <span v-if="coverage.last_imported_at" class="bank-coverage__import">
      {{ t("bankCoverage.lastImported", { date: formatKyivDate(coverage.last_imported_at, locale) }) }}
    </span>
  </p>
</template>

<script setup lang="ts">
  import { format, parseISO } from "date-fns";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { type BankCoverageOut, getBankCoverage } from "@shared/api/billing";
  import { formatKyivDate } from "@shared/utils/format";

  const { t } = useI18n();
  const locale = navigator.language;

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
    color: color-mix(in srgb, var(--s-content-color), transparent 30%);
    font-size: 0.85rem;
    margin: 0;
    min-width: 0;

    &--awaiting {
      color: var(--s-amber-500);
    }

    &__import {
      display: block;
    }
  }
</style>

<template>
  <p v-if="shortfall?.active && shortfall.due_date" class="shortfall" role="status">
    {{
      t("shortfall.notice", {
        date: format(parseISO(shortfall.due_date), "dd.MM"),
        amount: formatUah(toDecimal(shortfall.owed_uah), locale),
      })
    }}
  </p>
</template>

<script setup lang="ts">
  import { format, parseISO } from "date-fns";
  import { onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import { useCurrentHousehold } from "@/features/households/useCurrentHousehold";
  import { getShortfall, type ShortfallOut } from "@shared/api/billing";
  import { formatUah, toDecimal } from "@shared/utils/format";

  const { t } = useI18n();
  const { currentId } = useCurrentHousehold();
  const locale = navigator.language;

  const shortfall = ref<ShortfallOut | null>(null);

  // Advisory like the coverage notice: if it can't load, show nothing.
  async function load(): Promise<void> {
    try {
      shortfall.value = await getShortfall(currentId.value);
    } catch {
      shortfall.value = null;
    }
  }

  onMounted(load);
  watch(currentId, load);
</script>

<style scoped lang="scss">
  .shortfall {
    background: color-mix(in srgb, var(--s-amber-500), transparent 85%);
    border-radius: 0.5rem;
    color: var(--s-content-color);
    font-size: 0.9rem;
    margin: 0;
    min-width: 0;
    padding: 0.5rem 0.75rem;
  }
</style>

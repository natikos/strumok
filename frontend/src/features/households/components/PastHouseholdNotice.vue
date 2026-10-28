<template>
  <aside v-for="item in past" :key="item.household_id" class="past-notice" role="note">
    <InfoCircle aria-hidden="true" />
    <p class="past-notice__text">
      {{
        $t("ownership.noLongerOwner", {
          name: item.household_name,
          date: formatKyivDate(item.owned_until, intlLocale),
        })
      }}
    </p>
  </aside>
</template>

<script setup lang="ts">
  import { InfoCircle } from "@primeicons/vue";
  import { onMounted } from "vue";

  import { useHouseholdTenures } from "@features/households/useHouseholdTenures";
  import { useLocale } from "@features/i18n/composables/useLocale";
  import { formatKyivDate } from "@shared/utils/format";

  const { past, load } = useHouseholdTenures();
  const { intlLocale } = useLocale();

  onMounted(load);
</script>

<style scoped lang="scss">
  .past-notice {
    @include layout.row(var(--s-app-space-3), flex-start);
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    color: var(--s-content-color);
    padding: var(--s-app-space-3) var(--s-app-space-4);

    &__text {
      margin: 0;
      min-width: 0;
    }
  }
</style>

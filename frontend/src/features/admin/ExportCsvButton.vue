<template>
  <Button
    as="a"
    class="export-csv"
    size="small"
    severity="secondary"
    variant="outlined"
    icon="pi pi-download"
    :href="href"
    :label="t('admin.export')"
    download
  />
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import { API_BASE_URL } from "@shared/api/client";

  const props = defineProps<{ path: string }>();

  const { t, locale } = useI18n();

  // A plain link lets mobile Safari and Chrome handle the download natively;
  // the auth cookie rides along. Ukrainian Excel wants `;` and decimal commas.
  const href = computed(
    () =>
      `${API_BASE_URL}/admin/export/${props.path}${props.path.includes("?") ? "&" : "?"}format=${locale.value === "ua" ? "ua" : "standard"}`
  );
</script>

<style scoped lang="scss">
  .export-csv {
    align-self: flex-start;
  }
</style>

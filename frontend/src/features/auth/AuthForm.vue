<template>
  <Card>
    <template #title>{{ t("auth.title") }}</template>
    <template #content>
      <Form v-slot="$form">
        <InputText type="email" name="email" placeholder="placeholder@gmail.com" />
        <InputText type="password" name="password" placeholder="Password" />
        <Button type="submit" :label="t('submit')" :disabled="!$form.valid" />
      </Form>
    </template>
  </Card>
</template>

<script setup lang="ts">
  import { Form } from "@primevue/forms";
  import { useI18n } from "vue-i18n";

  const { t } = useI18n();
</script>

<style scoped>
  :deep(.p-card-title) {
    font-size: var(--font-size-xl);
    line-height: 1.2;
    margin-bottom: var(--space-6);
  }

  :deep(.p-card-content) {
    padding-top: 0;
  }

  :deep(.p-form) {
    display: grid;
    gap: var(--space-4);
  }
</style>

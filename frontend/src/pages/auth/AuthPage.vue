<template>
  <AuthLayout class="auth-page">
    <AuthForm />
  </AuthLayout>
</template>

<script setup lang="ts">
  import AuthForm from "@features/auth/AuthForm.vue";

  import AuthLayout from "./AuthLayout.vue";
</script>

<style scoped>
  .auth-page {
    align-items: center;
    background: var(--s-content-background);
    display: grid;
    min-height: calc(100vh - 4.5rem);
    padding: var(--space-4) 0;
  }
</style>

<template>
  <AuthLayout class="auth-page">
    <AuthForm />
  </AuthLayout>
</template>

<script setup lang="ts"></script>

<style scoped>
  .auth-page {
    align-items: center;
    display: grid;
    min-height: calc(100vh - 4.5rem);
    padding: var(--space-4) 0;
  }
</style>

<template>
  <div>
    <p>Strumok theme: {{ theme }}</p>
    <Button @click="toggleTheme">Toggle Theme</Button>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watchEffect } from "vue";
  const theme = ref(localStorage.getItem("theme") ?? "light");
  const isDark = computed(() => theme.value === "dark");

  const toggleTheme = () => {
    theme.value = isDark.value ? "light" : "dark";
    localStorage.setItem("theme", theme.value);
  };

  watchEffect(() => {
    document.documentElement.classList.toggle("dark", isDark.value);
  });
</script>

<style scoped lang="scss">
  div {
    padding: 1rem;
    background: var(--s-layout-panel-background);
  }
</style>

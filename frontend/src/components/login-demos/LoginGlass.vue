<template>
  <article class="variant variant-glass">
    <div class="variant-glass__blob blob-one"></div>
    <div class="variant-glass__blob blob-two"></div>
    <div class="variant-glass__blob blob-three"></div>
    <section class="variant-glass__panel">
      <LoginForm compact />
    </section>
  </article>
</template>

<script setup lang="ts">
  import LoginForm from "./LoginForm.vue";
</script>

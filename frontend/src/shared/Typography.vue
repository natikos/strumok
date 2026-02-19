<!-- eslint-disable vue/multi-word-component-names -->
<template>
  <component :is="variantMap[variant].tag" :class="['typography', `typography--${variant}`]">
    <slot />
  </component>
</template>

<script setup lang="ts">
  interface VariantMap {
    tag: keyof HTMLElementTagNameMap;
  }

  interface TypographyProps {
    variant?: "h1" | "h2" | "h3" | "title" | "subtitle" | "body" | "caption" | "label";
  }

  const { variant = "body" } = defineProps<TypographyProps>();

  const variantMap: Record<
    "h1" | "h2" | "h3" | "title" | "subtitle" | "body" | "caption" | "label",
    VariantMap
  > = {
    body: { tag: "p" },
    caption: { tag: "span" },
    h1: { tag: "h1" },
    h2: { tag: "h2" },
    h3: { tag: "h3" },
    label: { tag: "label" },
    subtitle: { tag: "h5" },
    title: { tag: "h4" },
  };
</script>

<style scoped>
  .typography {
    margin: 0;
    color: var(--s-content-color);
  }
  .typography--h1 {
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1.2;
  }
  .typography--h2 {
    font-size: 2rem;
    font-weight: 600;
    line-height: 1.3;
  }
  .typography--h3 {
    font-size: 1.5rem;
    font-weight: 500;
    line-height: 1.4;
  }
  .typography--title {
    font-size: 1.25rem;
    font-weight: 600;
    line-height: 1.3;
  }
  .typography--subtitle {
    font-size: 1.125rem;
    font-weight: 500;
    line-height: 1.4;
  }
  .typography--body {
    font-size: 1rem;
    font-weight: 400;
    line-height: 1.6;
  }
  .typography--caption {
    font-size: 0.875rem;
    font-weight: 400;
    line-height: 1.4;
  }
  .typography--label {
    font-size: 0.875rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    line-height: 1.4;
  }
</style>

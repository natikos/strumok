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
    min-width: 0;
    word-break: break-word;
  }

  .typography--h1 {
    font-size: clamp(1.35rem, 1.05rem + 1.5vw, 2.5rem);
    font-weight: 700;
    line-height: 1.15;
  }

  .typography--h2 {
    font-size: clamp(1.2rem, 1rem + 1.2vw, 2rem);
    font-weight: 600;
    line-height: 1.2;
  }

  .typography--h3 {
    font-size: clamp(1.1rem, 0.98rem + 0.8vw, 1.5rem);
    font-weight: 500;
    line-height: 1.25;
  }

  .typography--title {
    font-size: clamp(1.05rem, 0.95rem + 0.5vw, 1.25rem);
    font-weight: 600;
    line-height: 1.3;
  }

  .typography--subtitle {
    font-size: clamp(0.92rem, 0.88rem + 0.3vw, 1.05rem);
    font-weight: 500;
    line-height: 1.4;
  }

  .typography--body {
    font-size: clamp(0.95rem, 0.93rem + 0.2vw, 1rem);
    font-weight: 400;
    line-height: 1.55;
  }

  .typography--caption {
    font-size: clamp(0.74rem, 0.72rem + 0.08vw, 0.8rem);
    font-weight: 400;
    line-height: 1.4;
  }

  .typography--label {
    font-size: clamp(0.7rem, 0.68rem + 0.1vw, 0.76rem);
    font-weight: 600;
    letter-spacing: 0.01em;
    line-height: 1.4;
    text-transform: uppercase;
  }
</style>

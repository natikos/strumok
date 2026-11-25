<template>
  <div class="test-mode-banner" role="note">
    <div class="test-mode-banner__track">
      <span class="test-mode-banner__text">{{ $t("testMode.banner") }}</span>
      <span class="test-mode-banner__text" aria-hidden="true">{{ $t("testMode.banner") }}</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
  .test-mode-banner {
    background: var(--s-amber-500);
    color: var(--s-amber-950);
    font-weight: 600;
    font-size: 0.875rem;
    overflow: hidden;
    padding: var(--s-app-space-1) 0;
    width: 100%;

    &__track {
      display: flex;
      width: max-content;
      animation: test-mode-scroll 30s linear infinite;
    }

    &:hover &__track {
      animation-play-state: paused;
    }

    &__text {
      flex: none;
      padding-inline-end: 4rem;
      white-space: nowrap;
    }

    @media (prefers-reduced-motion: reduce) {
      &__track {
        animation: none;
        width: auto;
      }

      &__text {
        padding: 0 var(--s-app-space-2);
        white-space: normal;
      }

      &__text[aria-hidden="true"] {
        display: none;
      }
    }
  }

  @keyframes test-mode-scroll {
    to {
      transform: translateX(-50%);
    }
  }
</style>

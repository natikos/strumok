<template>
  <div class="app-loader">
    <img alt="" class="app-loader__icon" src="/icon.svg" />
  </div>
</template>

<style scoped lang="scss">
  .app-loader {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .app-loader__icon {
    width: 5rem;
    height: 5rem;
    animation: pulse-glow 1.6s ease-in-out infinite;
  }

  @keyframes pulse-glow {
    0%,
    100% {
      opacity: 0.4;
      filter: drop-shadow(0 0 0 transparent);
      transform: scale(0.95);
    }

    50% {
      opacity: 1;
      filter: drop-shadow(0 0 12px rgba(29, 78, 216, 0.4));
      transform: scale(1);
    }
  }
</style>

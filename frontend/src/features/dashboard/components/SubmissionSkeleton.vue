<template>
  <div class="submission-skeleton" aria-busy="true">
    <Skeleton height="1.75rem" width="80%" />
    <Skeleton height="1rem" width="60%" />
    <Skeleton height="0.375rem" width="100%" />
    <Skeleton height="2.75rem" class="submission-skeleton__input" />
    <Skeleton height="3.25rem" class="submission-skeleton__input" />
  </div>
</template>

<style scoped lang="scss">
  .submission-skeleton {
    @include layout.stack(var(--s-app-space-3));

    @include layout.respond-to("lg") {
      gap: var(--s-app-space-4);
    }

    &__input {
      border-radius: var(--s-app-radius-md);
    }
  }
</style>

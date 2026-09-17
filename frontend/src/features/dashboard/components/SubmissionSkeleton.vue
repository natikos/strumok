<template>
  <div class="submission-skeleton">
    <Skeleton height="1.75rem" width="80%" class="submission-skeleton__row" />
    <Skeleton height="1rem" width="60%" class="submission-skeleton__row" />
    <Skeleton height="0.375rem" width="100%" class="submission-skeleton__row" />
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

    &__row {
      border-radius: var(--s-app-radius-sm);
    }

    &__input {
      border-radius: var(--s-app-radius-md);
    }
  }
</style>

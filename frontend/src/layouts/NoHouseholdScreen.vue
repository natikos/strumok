<template>
  <AuthLayout class="no-household-screen">
    <Card class="no-household-card">
      <template #content>
        <div class="no-household-card__content">
          <i class="pi pi-home no-household-card__icon" aria-hidden="true"></i>

          <Typography class="no-household-card__title" variant="h1">
            {{ $t("noHousehold.title") }}
          </Typography>

          <Typography class="no-household-card__body" variant="subtitle">
            {{ $t("noHousehold.body") }}
          </Typography>

          <Typography v-if="stillNotAssigned" class="no-household-card__notice" variant="subtitle">
            {{ $t("noHousehold.stillNotAssigned") }}
          </Typography>

          <div class="no-household-card__actions">
            <Button
              class="no-household-card__button"
              :disabled="isChecking"
              :loading="isChecking"
              :label="$t('noHousehold.checkAgain')"
              @click="handleCheckAgain"
            />
            <Button
              class="no-household-card__button"
              :label="$t('nav.logout')"
              severity="contrast"
              variant="outlined"
              :disabled="isLoggingOut"
              @click="handleLogout"
            />
          </div>
        </div>
      </template>
    </Card>
  </AuthLayout>
</template>

<script setup lang="ts">
  import { ref } from "vue";
  import { useRouter } from "vue-router";

  import { getMe, logoutUser } from "@shared/api/auth";
  import type { components } from "@shared/api/generated/openapi";
  import { ROUTES } from "@shared/routing/routes";

  type UserOut = components["schemas"]["UserWithHouseholdsOut"];

  const router = useRouter();

  const isChecking = ref(false);
  const isLoggingOut = ref(false);
  const stillNotAssigned = ref(false);

  const emit = defineEmits<{
    unblocked: [me: UserOut];
  }>();

  async function handleCheckAgain(): Promise<void> {
    if (isChecking.value) {
      return;
    }

    isChecking.value = true;
    stillNotAssigned.value = false;

    try {
      const me = await getMe();

      if (me.households.length > 0) {
        emit("unblocked", me);
        return;
      }

      stillNotAssigned.value = true;
    } finally {
      isChecking.value = false;
    }
  }

  async function handleLogout(): Promise<void> {
    if (isLoggingOut.value) {
      return;
    }

    isLoggingOut.value = true;

    try {
      await logoutUser();
      await router.replace(ROUTES.auth);
    } finally {
      isLoggingOut.value = false;
    }
  }
</script>

<style scoped lang="scss">
  .no-household-card {
    width: min(100%, 31.25rem);
  }

  .no-household-card__content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
    text-align: center;
  }

  .no-household-card__icon {
    font-size: 2rem;
    color: color-mix(in srgb, var(--s-content-color), transparent 65%);
  }

  .no-household-card__body {
    max-width: 28rem;
  }

  .no-household-card__notice {
    color: var(--s-red-500);
  }

  .no-household-card__actions {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    width: 100%;
  }

  .no-household-card__button {
    width: 100%;
    min-height: 2.75rem;
  }
</style>

<template>
  <AuthLayout class="confirm-email-change-page">
    <Card class="confirm-email-change-card">
      <template #content>
        <div class="confirm-email-change-card__content">
          <template v-if="state === 'pending'">
            <ProgressSpinner class="confirm-email-change-card__spinner" />
            <Typography variant="h1">{{ $t("confirmEmailChange.confirming") }}</Typography>
          </template>

          <template v-else-if="state === 'confirmed'">
            <Typography variant="h1">{{ $t("confirmEmailChange.successTitle") }}</Typography>
            <Typography variant="subtitle">{{ $t("confirmEmailChange.successBody") }}</Typography>
            <Button :label="$t('confirmEmailChange.signIn')" @click="goToSignIn" />
          </template>

          <template v-else>
            <Typography variant="h1">{{ $t("confirmEmailChange.errorExpired") }}</Typography>
            <Button :label="$t('confirmEmailChange.signIn')" @click="goToSignIn" />
          </template>
        </div>
      </template>
    </Card>
  </AuthLayout>
</template>

<script setup lang="ts">
  import { onMounted, ref } from "vue";
  import { useRoute, useRouter } from "vue-router";

  import { confirmEmailChange } from "@shared/api/auth";
  import { ROUTES } from "@shared/routing/routes";

  const route = useRoute();
  const router = useRouter();
  const state = ref<"confirmed" | "error" | "pending">("pending");

  async function goToSignIn(): Promise<void> {
    await router.replace(ROUTES.auth);
  }

  onMounted(async () => {
    const token = route.query["token"];

    if (typeof token !== "string") {
      state.value = "error";
      return;
    }

    try {
      await confirmEmailChange(token);
      state.value = "confirmed";
    } catch {
      state.value = "error";
    }
  });
</script>

<style scoped lang="scss">
  .confirm-email-change-card {
    width: min(100%, 31.25rem);

    &__content {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
      text-align: center;
    }

    &__spinner {
      height: 3rem;
      margin: 0 auto;
      width: 3rem;
    }
  }
</style>

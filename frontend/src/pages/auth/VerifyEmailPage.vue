<template>
  <AuthLayout class="verify-email-page">
    <Card class="verify-email-card">
      <template #content>
        <div v-if="tokenState === 'pending'" class="verify-email-card__content">
          <ProgressSpinner class="verify-email-card__spinner" />
          <Typography class="verify-email-card__title" variant="h1">
            {{ $t("verifyEmail.confirming") }}
          </Typography>
        </div>

        <div v-else-if="tokenState === 'confirmed'" class="verify-email-card__content">
          <Typography class="verify-email-card__title" variant="h1">
            {{ $t("verifyEmail.successTitle") }}
          </Typography>
          <Typography class="verify-email-card__subtitle" variant="subtitle">
            {{ $t("verifyEmail.successBody") }}
          </Typography>
          <Button
            class="verify-email-card__button"
            :label="$t('verifyEmail.goToDashboard')"
            @click="handleGoToDashboard"
          />
        </div>

        <div v-else class="verify-email-card__content">
          <Typography class="verify-email-card__title" variant="h1">
            {{ $t("verifyEmail.title", { name: firstName }) }}
          </Typography>

          <Typography class="verify-email-card__subtitle" variant="subtitle">
            {{ $t("verifyEmail.subtitle", { email: maskedEmail }) }}
          </Typography>

          <Typography
            v-if="tokenState === 'error'"
            class="verify-email-card__error"
            variant="subtitle"
          >
            {{ $t("verifyEmail.errorExpired") }}
          </Typography>

          <Typography
            v-if="sendState === 'failed'"
            class="verify-email-card__error"
            variant="subtitle"
          >
            {{ $t("verifyEmail.sendFailed") }}
          </Typography>

          <Typography v-if="stillNotVerified" class="verify-email-card__error" variant="subtitle">
            {{ $t("verifyEmail.stillNotVerified") }}
          </Typography>

          <div class="verify-email-card__actions">
            <Button
              class="verify-email-card__button"
              :disabled="sendState === 'sending' || cooldownSeconds > 0"
              :label="sendButtonLabel"
              @click="handleSendVerificationLink"
            />
            <Button
              class="verify-email-card__button"
              :disabled="isChecking"
              :label="$t('verifyEmail.checkButton')"
              severity="secondary"
              @click="handleCheckVerification"
            />
            <Button
              class="verify-email-card__button"
              :label="$t('nav.logout')"
              severity="contrast"
              variant="outlined"
              @click="handleLogout"
            />
          </div>
        </div>
      </template>
    </Card>
  </AuthLayout>
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";
  import { useRoute, useRouter } from "vue-router";

  import {
    ApiError,
    confirmEmailVerification,
    getMe,
    logoutUser,
    sendVerificationEmailLink,
  } from "@shared/api/auth";
  import { ROUTES } from "@shared/routing/routes";

  const RESEND_COOLDOWN_SECONDS = 180;

  const firstName = ref("");
  const maskedEmail = ref("");
  const isChecking = ref(false);
  const tokenState = ref<"idle" | "pending" | "confirmed" | "error">("idle");
  const sendState = ref<"idle" | "sending" | "failed">("idle");
  const stillNotVerified = ref(false);
  const cooldownSeconds = ref(0);
  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();

  let cooldownTimer: ReturnType<typeof setInterval> | null = null;

  const sendButtonLabel = computed(() => {
    if (cooldownSeconds.value > 0) {
      const minutes = Math.floor(cooldownSeconds.value / 60);
      const seconds = cooldownSeconds.value % 60;
      const timer = `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
      return t("verifyEmail.resendCooldown", { timer });
    }

    return t("verifyEmail.sendButton");
  });

  function startCooldown(seconds = RESEND_COOLDOWN_SECONDS): void {
    cooldownSeconds.value = seconds;

    if (cooldownTimer) {
      clearInterval(cooldownTimer);
    }

    cooldownTimer = setInterval(() => {
      if (cooldownSeconds.value <= 1) {
        cooldownSeconds.value = 0;
        if (cooldownTimer) {
          clearInterval(cooldownTimer);
          cooldownTimer = null;
        }
        return;
      }

      cooldownSeconds.value -= 1;
    }, 1000);
  }

  function maskEmail(email: string): string {
    const [localPart, domain] = email.split("@");
    if (!localPart || !domain) {
      return email;
    }

    const visibleStart = localPart.slice(0, 1);
    const maskedMiddle = "*".repeat(Math.max(localPart.length - 1, 1));
    return `${visibleStart}${maskedMiddle}@${domain}`;
  }

  async function syncUserState(): Promise<boolean> {
    const me = await getMe();

    if (me.email_verified) {
      await router.replace(ROUTES.root);
      return true;
    }

    firstName.value = me.first_name;
    maskedEmail.value = maskEmail(me.email);

    if (me.verification_email_retry_after_seconds > 0) {
      startCooldown(me.verification_email_retry_after_seconds);
    }

    return false;
  }

  async function handleSendVerificationLink(): Promise<void> {
    if (cooldownSeconds.value > 0 || sendState.value === "sending") {
      return;
    }

    sendState.value = "sending";
    stillNotVerified.value = false;

    try {
      await sendVerificationEmailLink();
      startCooldown();
      sendState.value = "idle";
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 429) {
        startCooldown();
        sendState.value = "idle";
      } else {
        sendState.value = "failed";
      }
    }
  }

  async function handleConfirmToken(token: string): Promise<void> {
    tokenState.value = "pending";

    try {
      await confirmEmailVerification(token);
      tokenState.value = "confirmed";
    } catch {
      tokenState.value = "error";
      await syncUserState();
    }
  }

  async function handleGoToDashboard(): Promise<void> {
    await router.replace(ROUTES.root);
  }

  async function handleCheckVerification(): Promise<void> {
    isChecking.value = true;
    stillNotVerified.value = false;

    try {
      const verified = await syncUserState();
      stillNotVerified.value = !verified;
    } finally {
      isChecking.value = false;
    }
  }

  async function handleLogout(): Promise<void> {
    try {
      await logoutUser();
    } finally {
      await router.replace(ROUTES.auth);
    }
  }

  onMounted(async () => {
    const token = route.query["token"];

    if (typeof token === "string") {
      await handleConfirmToken(token);
      return;
    }

    try {
      await syncUserState();
    } catch {
      await router.replace(ROUTES.auth);
    }
  });

  onBeforeUnmount(() => {
    if (cooldownTimer) {
      clearInterval(cooldownTimer);
      cooldownTimer = null;
    }
  });
</script>

<style scoped lang="scss">
  .verify-email-card {
    width: min(100%, 31.25rem);
  }

  .verify-email-card__content {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    text-align: center;
  }

  .verify-email-card__actions {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .verify-email-card__button {
    width: 100%;
  }

  .verify-email-card__spinner {
    width: 3rem;
    height: 3rem;
    margin: 0 auto;
  }

  .verify-email-card__error {
    color: var(--s-red-500);
  }
</style>

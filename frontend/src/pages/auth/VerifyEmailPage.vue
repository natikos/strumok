<template>
  <AuthLayout class="verify-email-page">
    <Card class="verify-email-card">
      <template #content>
        <div class="verify-email-card__content">
          <Typography class="verify-email-card__title" variant="h1">
            {{ $t("verifyEmail.title", { name: firstName }) }}
          </Typography>

          <Typography class="verify-email-card__subtitle" variant="subtitle">
            {{ $t("verifyEmail.subtitle", { email: maskedEmail }) }}
          </Typography>

          <div class="verify-email-card__actions">
            <Button
              class="verify-email-card__button"
              :disabled="isSending || cooldownSeconds > 0"
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
              :label="$t('dashboard.logout')"
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
  import { useRouter } from "vue-router";

  import { ApiError, getMe, logoutUser, sendVerificationEmailLink } from "@shared/api/auth";
  import { ROUTES } from "@shared/routing/routes";

  const RESEND_COOLDOWN_SECONDS = 180;

  const firstName = ref("");
  const maskedEmail = ref("");
  const isSending = ref(false);
  const isChecking = ref(false);
  const cooldownSeconds = ref(0);
  const router = useRouter();
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

  async function syncUserState(): Promise<void> {
    const me = await getMe();

    if (me.email_verified) {
      await router.replace(ROUTES.dashboard);
      return;
    }

    firstName.value = me.first_name;
    maskedEmail.value = maskEmail(me.email);

    if (me.verification_email_retry_after_seconds > 0) {
      startCooldown(me.verification_email_retry_after_seconds);
    }
  }

  async function handleSendVerificationLink(): Promise<void> {
    if (cooldownSeconds.value > 0 || isSending.value) {
      return;
    }

    isSending.value = true;

    try {
      await sendVerificationEmailLink();
      startCooldown();
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 429) {
        startCooldown();
      }
    } finally {
      isSending.value = false;
    }
  }

  async function handleCheckVerification(): Promise<void> {
    isChecking.value = true;

    try {
      await syncUserState();
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
</style>

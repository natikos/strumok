<template>
  <AuthLayout class="forgot-password-page">
    <Card class="forgot-password-card">
      <template #title>
        <Typography variant="h1">{{ $t("auth.forgotTitle") }}</Typography>
      </template>

      <template #content>
        <div class="forgot-password-card__content">
          <template v-if="!isSent">
            <Typography variant="subtitle">{{ $t("auth.forgotSubtitle") }}</Typography>
            <Form v-slot="$form" class="forgot-password-card__form" :resolver="resolver" @submit="handleSubmit">
              <FormFieldControl
                id="forgot-email"
                name="email"
                type="email"
                autocomplete="username"
                label-key="auth.email"
                placeholder-key="auth.emailPlaceholder"
                :disabled="isSubmitting"
              />
              <Button
                fluid
                type="submit"
                :label="$t('auth.forgotSubmit')"
                :disabled="isSubmitting || !$form.valid"
                :loading="isSubmitting"
              />
            </Form>
          </template>

          <template v-else>
            <Message severity="success" role="status">{{ $t("auth.forgotSent") }}</Message>
            <Button
              fluid
              severity="secondary"
              :disabled="cooldownSeconds > 0"
              :label="
                cooldownSeconds > 0
                  ? $t('auth.resendIn', { timer: cooldownTimer })
                  : $t('auth.forgotSubmit')
              "
              @click="resend"
            />
          </template>

          <RouterLink class="forgot-password-card__back" :to="ROUTES.auth">
            {{ $t("auth.backToLogin") }}
          </RouterLink>
        </div>
      </template>
    </Card>
  </AuthLayout>
</template>

<script setup lang="ts">
  import { Form } from "@primevue/forms";
  import { zodResolver } from "@primevue/forms/resolvers/zod";
  import { ref } from "vue";
  import { z } from "zod";

  import type { FormSubmitEvent } from "@primevue/forms/form";
  import { requestPasswordReset } from "@shared/api/auth";
  import { useCountdown } from "@shared/composables/useCountdown";
  import FormFieldControl from "@shared/FormFieldControl.vue";
  import { ROUTES } from "@shared/routing/routes";

  const RESEND_COOLDOWN_SECONDS = 60;

  const isSent = ref(false);
  const isSubmitting = ref(false);
  const email = ref("");
  const { formatted: cooldownTimer, seconds: cooldownSeconds, start: startCooldown } = useCountdown();

  const schema = z.object({
    email: z
      .string({ error: "auth.requiredField" })
      .trim()
      .pipe(z.email("auth.invalidEmail")),
  });
  const resolver = zodResolver(schema);

  async function send(): Promise<void> {
    isSubmitting.value = true;

    try {
      await requestPasswordReset(email.value);
      isSent.value = true;
      startCooldown(RESEND_COOLDOWN_SECONDS);
    } catch {
      // The global error toast reports the failure.
    } finally {
      isSubmitting.value = false;
    }
  }

  async function handleSubmit(event: FormSubmitEvent): Promise<void> {
    const parsed = schema.safeParse(event.values);

    if (!event.valid || !parsed.success) {
      return;
    }

    email.value = parsed.data.email;
    await send();
  }

  async function resend(): Promise<void> {
    if (cooldownSeconds.value === 0) {
      await send();
    }
  }
</script>

<style scoped lang="scss">
  .forgot-password-card {
    width: min(100%, 31.25rem);

    &__content,
    &__form {
      @include layout.stack(var(--s-app-space-4));
      min-width: 0;
    }

    &__back {
      color: var(--p-primary-color);
      text-align: center;
    }
  }
</style>

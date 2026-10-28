<template>
  <Card class="auth-form">
    <template #title>
      <div class="auth-form__header">
        <Typography variant="h1" class="auth-form__title">
          {{ $t("auth.loginTitle") }}
        </Typography>
        <Typography variant="subtitle" class="auth-form__subtitle">
          {{ $t("auth.loginSubtitle") }}
        </Typography>
      </div>
    </template>

    <template #content>
      <div class="auth-form__content">
        <Form v-slot="$form" class="auth-form__fields" :resolver="resolver" @submit="handleSubmit">
          <FormFieldControl
            id="auth-email"
            name="email"
            type="email"
            autocomplete="username"
            label-key="auth.email"
            placeholder-key="auth.emailPlaceholder"
            :disabled="isSubmitting"
          />
          <FormFieldControl
            id="auth-password"
            name="password"
            type="password"
            :input-props="{
              autocomplete: 'current-password',
              name: 'password',
            }"
            label-key="auth.password"
            placeholder-key="auth.password"
            :disabled="isSubmitting"
          />

          <RouterLink class="auth-form__forgot" :to="ROUTES.forgotPassword">
            {{ $t("auth.forgotPassword") }}
          </RouterLink>

          <Button
            fluid
            type="submit"
            class="auth-form__submit"
            :label="$t('auth.loginSubmit')"
            :disabled="isSubmitting || !$form.valid || throttleSeconds > 0"
            :loading="isSubmitting"
          />
          <Message
            v-if="throttleSeconds > 0"
            class="auth-form__throttle"
            severity="error"
            role="alert"
          >
            {{ $t("auth.tooManyAttempts", { timer: throttleTimer }) }}
          </Message>
        </Form>
        <p class="auth-form__invite-note">{{ $t("auth.inviteNote") }}</p>
        <RouterLink class="auth-form__forgot" :to="ROUTES.privacy">
          {{ $t("privacy.link") }}
        </RouterLink>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
  import { Form } from "@primevue/forms";
  import { zodResolver } from "@primevue/forms/resolvers/zod";
  import { ref } from "vue";
  import { useRouter } from "vue-router";
  import { z } from "zod";

  import { useLocale } from "@features/i18n/composables/useLocale";
  import { getStoredTheme } from "@features/preferences/preferences.storage";
  import { useTheme } from "@features/theme/composables/useTheme";
  import type { FormSubmitEvent } from "@primevue/forms/form";
  import { ApiError, loginUser, updateMyPreferences } from "@shared/api/auth";
  import type { UserOut } from "@shared/api/auth";
  import { useCountdown } from "@shared/composables/useCountdown";
  import FormFieldControl from "@shared/FormFieldControl.vue";
  import { ROUTES } from "@shared/routing/routes";

  const router = useRouter();
  const { setLocale } = useLocale();
  const { setTheme } = useTheme();

  const isSubmitting = ref(false);
  const { formatted: throttleTimer, seconds: throttleSeconds, start: startThrottle } = useCountdown();

  const baseString = () =>
    z
      .string({
        error: "auth.requiredField",
      })
      .trim();

  const loginSchema = z.object({
    email: baseString().pipe(z.email("auth.invalidEmail")),
    password: baseString().min(1, "auth.requiredField"),
  });

  const resolver = zodResolver(loginSchema);

  async function handleSubmit(event: FormSubmitEvent): Promise<void> {
    const { valid, values } = event;
    if (!valid) {
      return;
    }

    isSubmitting.value = true;

    try {
      const { success, data } = loginSchema.safeParse(values);

      if (!success) {
        return;
      }

      let me: UserOut = await loginUser({ email: data.email, password: data.password });

      const selectedTheme = getStoredTheme();

      if (selectedTheme !== me.theme) {
        me = await updateMyPreferences({ theme: selectedTheme });
      }

      setTheme(me.theme);

      await router.push(me.email_verified ? ROUTES.root : ROUTES.verifyEmail);

      setLocale(me.language);
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 429) {
        startThrottle(error.retryAfterSeconds ?? 60);
        return;
      }

      // API errors are handled globally through client middleware + toast presenter.
      if (!(error instanceof ApiError) && error instanceof Error) {
        console.error(error);
      }
    } finally {
      isSubmitting.value = false;
    }
  }
</script>

<style scoped lang="scss">
  .auth-form {
    width: 100%;
  }

  .auth-form :deep(.p-card-body) {
    padding: var(--s-app-space-2);
  }

  .auth-form__header {
    @include layout.stack(var(--s-app-space-2));
  }

  .auth-form__content,
  .auth-form__fields {
    @include layout.stack(var(--s-app-space-3));
  }

  .auth-form__fields {
    gap: var(--s-app-space-3);
  }

  .auth-form__forgot {
    align-self: flex-start;
    color: var(--p-primary-color);
    font-size: 0.875rem;
  }

  .auth-form__throttle {
    min-width: 0;
  }

  .auth-form__invite-note {
    color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    font-size: 0.85rem;
    margin: 0;
    text-align: center;
  }

  .auth-form__submit {
    margin-top: var(--s-app-space-1);
    transition: transform 180ms ease;
  }

  @media (min-width: 21.25rem) {
    .auth-form :deep(.p-card-body) {
      padding: var(--s-app-space-3);
    }

    .auth-form__header {
      gap: var(--s-app-space-3);
    }

    .auth-form__content,
    .auth-form__fields {
      gap: var(--s-app-space-4);
    }
  }

  @media (min-width: 30rem) {
    .auth-form :deep(.p-card-body) {
      padding: var(--s-app-space-4);
    }

    .auth-form__fields {
      gap: var(--s-app-space-3);
    }
  }
</style>

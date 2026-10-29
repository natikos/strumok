<template>
  <AuthLayout class="set-password-page">
    <Card class="set-password-card">
      <template #title>
        <Typography variant="h1">{{ $t("auth.setTitle") }}</Typography>
      </template>

      <template #content>
        <div class="set-password-card__content">
          <template v-if="tokenState === 'error'">
            <Message severity="error" role="alert">{{ $t("auth.setExpired") }}</Message>
            <Button
              fluid
              severity="secondary"
              :label="$t('auth.backToLogin')"
              @click="goTo(ROUTES.auth)"
            />
          </template>

          <Form
            v-else
            v-slot="$form"
            class="set-password-card__form"
            :resolver="resolver"
            @submit="handleSubmit"
          >
            <div class="set-password-card__email">
              <label class="set-password-card__label" for="set-password-email">
                {{ $t("auth.email") }}
              </label>
              <InputText id="set-password-email" fluid readonly :model-value="email" />
              <span class="set-password-card__hint">{{ $t("auth.setSubtitle") }}</span>
            </div>
            <FormFieldControl
              id="set-password"
              name="password"
              type="password"
              :input-props="{ autocomplete: 'new-password', name: 'password' }"
              label-key="auth.password"
              placeholder-key="auth.password"
              :disabled="isSubmitting"
            />
            <FormFieldControl
              id="set-confirm-password"
              name="confirmPassword"
              type="password"
              :input-props="{ autocomplete: 'new-password', name: 'confirmPassword' }"
              label-key="auth.confirmPassword"
              placeholder-key="auth.confirmPassword"
              :disabled="isSubmitting"
            />
            <Button
              fluid
              type="submit"
              :label="$t('auth.setSubmit')"
              :disabled="isSubmitting || !$form.valid"
              :loading="isSubmitting"
            />
          </Form>
        </div>
      </template>
    </Card>
  </AuthLayout>
</template>

<script setup lang="ts">
  import { Form } from "@primevue/forms";
  import { zodResolver } from "@primevue/forms/resolvers/zod";
  import { useToast } from "primevue/usetoast";
  import { ref } from "vue";
  import { useI18n } from "vue-i18n";
  import { useRoute, useRouter } from "vue-router";
  import { z } from "zod";

  import { useLocale } from "@features/i18n/composables/useLocale";
  import type { FormSubmitEvent } from "@primevue/forms/form";
  import { ApiError, confirmPasswordReset } from "@shared/api/auth";
  import FormFieldControl from "@shared/FormFieldControl.vue";
  import { ROUTES } from "@shared/routing/routes";

  const route = useRoute();
  const router = useRouter();
  const toast = useToast();
  const { setLocale } = useLocale();
  const { t } = useI18n();

  const token = typeof route.query["token"] === "string" ? route.query["token"] : "";
  const tokenState = ref<"error" | "idle">(token ? "idle" : "error");
  const isSubmitting = ref(false);

  // Display only: the server re-checks the token when the password is set.
  function readEmail(jwt: string): string {
    try {
      const payload = JSON.parse(
        atob((jwt.split(".")[1] ?? "").replace(/-/g, "+").replace(/_/g, "/"))
      ) as {
        email?: unknown;
      };
      return typeof payload.email === "string" ? payload.email : "";
    } catch {
      return "";
    }
  }

  const email = readEmail(token);

  const schema = z
    .object({
      confirmPassword: z.string({ error: "auth.requiredField" }).min(8, "auth.passwordMinLength"),
      password: z.string({ error: "auth.requiredField" }).min(8, "auth.passwordMinLength"),
    })
    .refine((data) => data.password === data.confirmPassword, {
      message: "auth.passwordMismatch",
      path: ["confirmPassword"],
    });
  const resolver = zodResolver(schema);

  async function goTo(path: string): Promise<void> {
    await router.replace(path);
  }

  async function handleSubmit(event: FormSubmitEvent): Promise<void> {
    const parsed = schema.safeParse(event.values);

    if (!event.valid || !parsed.success) {
      return;
    }

    isSubmitting.value = true;

    try {
      const me = await confirmPasswordReset(token, parsed.data.password);
      setLocale(me.language);
      toast.add({ detail: t("auth.setDone"), life: 6000, severity: "success" });
      await goTo(ROUTES.root);
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 400) {
        tokenState.value = "error";
      }
    } finally {
      isSubmitting.value = false;
    }
  }
</script>

<style scoped lang="scss">
  .set-password-card {
    width: min(100%, 31.25rem);

    &__content,
    &__form {
      @include layout.stack(var(--s-app-space-4));
      min-width: 0;
    }

    &__email {
      @include layout.stack(var(--s-app-space-2));
    }

    &__label {
      font-size: 0.85rem;
      font-weight: 500;
    }

    &__hint {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      font-size: 0.8rem;
    }
  }
</style>

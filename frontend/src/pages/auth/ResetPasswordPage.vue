<template>
  <AuthLayout class="reset-password-page">
    <Card class="reset-password-card">
      <template #title>
        <Typography variant="h1">{{ $t("auth.resetTitle") }}</Typography>
      </template>

      <template #content>
        <div class="reset-password-card__content">
          <template v-if="tokenState === 'error'">
            <Message severity="error" role="alert">{{ $t("auth.resetExpired") }}</Message>
            <Button fluid :label="$t('auth.requestNewLink')" @click="goTo(ROUTES.forgotPassword)" />
          </template>

          <Form
            v-else
            v-slot="$form"
            class="reset-password-card__form"
            :resolver="resolver"
            @submit="handleSubmit"
          >
            <FormFieldControl
              id="reset-password"
              name="password"
              type="password"
              :input-props="{ autocomplete: 'new-password', name: 'password' }"
              label-key="auth.password"
              placeholder-key="auth.password"
              :disabled="isSubmitting"
            />
            <FormFieldControl
              id="reset-confirm-password"
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
              :label="$t('auth.resetSubmit')"
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

  import type { FormSubmitEvent } from "@primevue/forms/form";
  import { ApiError, confirmPasswordReset } from "@shared/api/auth";
  import FormFieldControl from "@shared/FormFieldControl.vue";
  import { ROUTES } from "@shared/routing/routes";

  const route = useRoute();
  const router = useRouter();
  const toast = useToast();
  const { t } = useI18n();

  const token = typeof route.query["token"] === "string" ? route.query["token"] : "";
  const tokenState = ref<"error" | "idle">(token ? "idle" : "error");
  const isSubmitting = ref(false);

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
      await confirmPasswordReset(token, parsed.data.password);
      toast.add({ detail: t("auth.resetDone"), life: 6000, severity: "success" });
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
  .reset-password-card {
    width: min(100%, 31.25rem);

    &__content,
    &__form {
      @include layout.stack(var(--s-app-space-4));
      min-width: 0;
    }
  }
</style>

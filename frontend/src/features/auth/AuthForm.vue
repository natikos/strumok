<template>
  <Card class="auth-form">
    <template #title>
      <div class="auth-form__header">
        <Typography variant="h1" class="auth-form__title">
          {{ $t(`auth.${mode}Title`) }}
        </Typography>
        <Typography variant="subtitle" class="auth-form__subtitle">
          {{ $t(`auth.${mode}Subtitle`) }}
        </Typography>
      </div>
    </template>

    <template #content>
      <div class="auth-form__content">
        <Form v-slot="$form" class="auth-form__fields" :resolver="resolver" @submit="handleSubmit">
          <SelectButton
            v-model="mode"
            :allow-empty="false"
            :options="[
              { label: $t('auth.login'), value: 'login' },
              { label: $t('auth.register'), value: 'register' },
            ]"
            option-label="label"
            option-value="value"
            class="auth-form__mode"
            :disabled="isSubmitting"
            @update:model-value="$form.reset()"
          />

          <div
            class="auth-form__expand"
            :class="{ 'auth-form__expand--open': mode === 'register' }"
          >
            <div class="auth-form__extra auth-form__extra--names">
              <FormFieldControl
                id="auth-first-name"
                name="firstName"
                label-key="auth.firstName"
                placeholder-key="auth.firstName"
                :disabled="isSubmitting"
              />
              <FormFieldControl
                id="auth-last-name"
                name="lastName"
                label-key="auth.lastName"
                placeholder-key="auth.lastName"
                :disabled="isSubmitting"
              />
            </div>
          </div>

          <FormFieldControl
            id="auth-email"
            name="email"
            type="email"
            label-key="auth.email"
            placeholder-key="auth.emailPlaceholder"
            :disabled="isSubmitting"
          />
          <FormFieldControl
            id="auth-password"
            name="password"
            type="password"
            label-key="auth.password"
            placeholder-key="auth.password"
            :disabled="isSubmitting"
          />

          <div
            class="auth-form__expand"
            :class="{ 'auth-form__expand--open': mode === 'register' }"
          >
            <div class="auth-form__extra">
              <FormFieldControl
                id="auth-confirm-password"
                name="confirmPassword"
                type="password"
                label-key="auth.confirmPassword"
                placeholder-key="auth.confirmPassword"
                :disabled="isSubmitting"
              />
            </div>
          </div>

          <Button
            fluid
            type="submit"
            class="auth-form__submit"
            :label="$t(`auth.${mode}Submit`)"
            :disabled="isSubmitting || !$form.valid"
            :loading="isSubmitting"
          />
        </Form>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
  import { Form } from "@primevue/forms";
  import { zodResolver } from "@primevue/forms/resolvers/zod";
  import { computed, ref } from "vue";
  import { useRouter } from "vue-router";
  import { z } from "zod";

  import type { FormSubmitEvent } from "@primevue/forms/form";
  import { ApiError, loginUser, registerUser } from "@shared/api/auth";
  import FormFieldControl from "@shared/FormFieldControl.vue";
  import { ROUTES } from "@shared/routing/routes";

  type AuthMode = "login" | "register";

  const router = useRouter();

  const mode = ref<AuthMode>("login");
  const isSubmitting = ref(false);

  const baseString = () =>
    z
      .string({
        error: "auth.requiredField",
      })
      .trim();

  const isRegisterMode = computed(() => mode.value === "register");
  const emailSchema = baseString().pipe(z.email("auth.invalidEmail"));

  const loginSchema = z.object({
    email: emailSchema,
    password: baseString().min(1, "auth.requiredField"),
  });

  const registerSchema = z
    .object({
      confirmPassword: baseString().min(8, "auth.passwordMinLength"),
      email: emailSchema,
      firstName: baseString().min(2, "auth.nameMinLength"),
      lastName: baseString().min(2, "auth.nameMinLength"),
      password: baseString().min(8, "auth.passwordMinLength"),
    })
    .refine((data) => data["password"] === data["confirmPassword"], {
      message: "auth.passwordMismatch",
      path: ["confirmPassword"],
    });

  const resolver = (options: { values: Record<string, unknown> }) =>
    isRegisterMode.value ? zodResolver(registerSchema)(options) : zodResolver(loginSchema)(options);

  async function handleSubmit(event: FormSubmitEvent): Promise<void> {
    const { valid, values } = event;
    if (!valid) {
      return;
    }

    isSubmitting.value = true;

    try {
      if (isRegisterMode.value) {
        const { success, data } = registerSchema.safeParse(values);

        if (!success) {
          return;
        }

        const { email, firstName, lastName, password } = data;

        await registerUser({
          email,
          first_name: firstName,
          last_name: lastName,
          password,
        });
      } else {
        const { success, data } = loginSchema.safeParse(values);

        if (!success) {
          return;
        }

        const { email, password } = data;

        await loginUser({
          email,
          password,
        });
      }

      await router.push(ROUTES.dashboard);
    } catch (error: unknown) {
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

  .auth-form__mode {
    margin-bottom: var(--s-app-space-1);
    margin-top: 0;
    width: 100%;
  }

  .auth-form__content,
  .auth-form__fields,
  .auth-form__extra {
    @include layout.stack(var(--s-app-space-3));
  }

  .auth-form__fields {
    gap: var(--s-app-space-3);
  }

  .auth-form__submit {
    margin-top: var(--s-app-space-1);
    transition: transform 180ms ease;
  }

  .auth-form__expand {
    display: grid;
    grid-template-rows: 0fr;
    overflow: hidden;
    transition:
      grid-template-rows 240ms ease,
      opacity 240ms ease;
  }

  .auth-form__expand > .auth-form__extra {
    min-height: 0;
    opacity: 0;
    transition: opacity 180ms ease;
  }

  .auth-form__expand--open {
    grid-template-rows: 1fr;
  }

  .auth-form__expand--open > .auth-form__extra {
    opacity: 1;
  }

  @media (min-width: 21.25rem) {
    .auth-form :deep(.p-card-body) {
      padding: var(--s-app-space-3);
    }

    .auth-form__header {
      gap: var(--s-app-space-3);
    }

    .auth-form__mode {
      margin-bottom: var(--s-app-space-2);
      margin-top: var(--s-app-space-1);
    }

    .auth-form__content,
    .auth-form__fields,
    .auth-form__extra {
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

  @media (min-width: 42rem) {
    .auth-form__extra--names {
      column-gap: var(--s-app-space-3);
      display: grid;
      grid-template-columns: 1fr 1fr;
      row-gap: var(--s-app-space-2);
    }
  }
</style>

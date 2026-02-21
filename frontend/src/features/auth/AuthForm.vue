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
              <FormField v-slot="$field" name="firstName" class="auth-form__field">
                <Typography variant="label" class="auth-form__label" for="auth-first-name">
                  {{ $t("auth.firstName") }}
                </Typography>
                <InputText
                  id="auth-first-name"
                  class="auth-form__control"
                  type="text"
                  name="firstName"
                  :placeholder="$t('auth.firstName')"
                  :disabled="isSubmitting"
                  :invalid="$field.invalid"
                />
                <div class="auth-form__field-message">
                  <Transition name="field-error">
                    <Typography
                      v-if="$field.invalid && $field.error?.message"
                      variant="caption"
                      class="auth-form__field-error"
                    >
                      {{ $t($field.error.message) }}
                    </Typography>
                  </Transition>
                </div>
              </FormField>
              <FormField v-slot="$field" name="lastName" class="auth-form__field">
                <Typography variant="label" class="auth-form__label" for="auth-last-name">
                  {{ $t("auth.lastName") }}
                </Typography>
                <InputText
                  id="auth-last-name"
                  class="auth-form__control"
                  type="text"
                  name="lastName"
                  :placeholder="$t('auth.lastName')"
                  :disabled="isSubmitting"
                  :invalid="$field.invalid"
                />
                <div class="auth-form__field-message">
                  <Transition name="field-error">
                    <Typography
                      v-if="$field.invalid && $field.error?.message"
                      variant="caption"
                      class="auth-form__field-error"
                    >
                      {{ $t($field.error.message) }}
                    </Typography>
                  </Transition>
                </div>
              </FormField>
            </div>
          </div>

          <FormField v-slot="$field" name="email" class="auth-form__field">
            <Typography variant="label" class="auth-form__label" for="auth-email">
              {{ $t("auth.email") }}
            </Typography>
            <InputText
              id="auth-email"
              class="auth-form__control"
              type="email"
              name="email"
              :placeholder="$t('auth.emailPlaceholder')"
              :disabled="isSubmitting"
              :invalid="$field.invalid"
            />
            <div class="auth-form__field-message">
              <Transition name="field-error">
                <Typography
                  v-if="$field.invalid && $field.error?.message"
                  variant="caption"
                  class="auth-form__field-error"
                >
                  {{ $t($field.error.message) }}
                </Typography>
              </Transition>
            </div>
          </FormField>
          <FormField v-slot="$field" name="password" class="auth-form__field">
            <Typography variant="label" class="auth-form__label" for="auth-password">
              {{ $t("auth.password") }}
            </Typography>
            <Password
              id="auth-password"
              class="auth-form__control"
              name="password"
              :feedback="false"
              fluid
              toggle-mask
              :placeholder="$t('auth.password')"
              :disabled="isSubmitting"
              :invalid="$field.invalid"
            />
            <div class="auth-form__field-message">
              <Transition name="field-error">
                <Typography
                  v-if="$field.invalid && $field.error?.message"
                  variant="caption"
                  class="auth-form__field-error"
                >
                  {{ $t($field.error.message) }}
                </Typography>
              </Transition>
            </div>
          </FormField>

          <div
            class="auth-form__expand"
            :class="{ 'auth-form__expand--open': mode === 'register' }"
          >
            <div class="auth-form__extra">
              <FormField v-slot="$field" name="confirmPassword" class="auth-form__field">
                <Typography variant="label" class="auth-form__label" for="auth-confirm-password">
                  {{ $t("auth.confirmPassword") }}
                </Typography>
                <Password
                  id="auth-confirm-password"
                  class="auth-form__control"
                  name="confirmPassword"
                  :feedback="false"
                  fluid
                  toggle-mask
                  :placeholder="$t('auth.confirmPassword')"
                  :disabled="isSubmitting"
                  :invalid="$field.invalid"
                />
                <div class="auth-form__field-message">
                  <Transition name="field-error">
                    <Typography
                      v-if="$field.invalid && $field.error?.message"
                      variant="caption"
                      class="auth-form__field-error"
                    >
                      {{ $t($field.error.message) }}
                    </Typography>
                  </Transition>
                </div>
              </FormField>
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
  import { Form, FormField } from "@primevue/forms";
  import type { FormSubmitEvent } from "@primevue/forms/form";
  import { zodResolver } from "@primevue/forms/resolvers/zod";
  import { ApiError, loginUser, registerUser } from "@shared/api/auth";
  import { computed, ref } from "vue";
  import { useRouter } from "vue-router";
  import { z } from "zod";

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

      await router.push("/demo");
    } catch (error: unknown) {
      if (!(error instanceof ApiError)) {
        // Keep noisy logs for unexpected exceptions while showing no global form error by design.
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

  .auth-form__header {
    @include layout.stack(var(--s-app-space-3));
  }

  .auth-form__mode {
    margin-bottom: var(--s-app-space-2);
    margin-top: var(--s-app-space-1);
    width: 100%;
  }

  .auth-form__content,
  .auth-form__fields,
  .auth-form__extra {
    @include layout.stack(var(--s-app-space-4));
  }

  .auth-form__fields {
    gap: var(--s-app-space-3);
  }

  .auth-form__field {
    min-width: 0;
  }

  .auth-form__control {
    width: 100%;
  }

  .auth-form :deep(.p-password-toggle-mask-icon) {
    cursor: pointer;
  }

  .auth-form__submit {
    margin-top: var(--s-app-space-1);
    transition: transform 180ms ease;
  }

  .auth-form__field-error {
    color: var(--s-red-500);
  }

  .field-error-enter-active,
  .field-error-leave-active {
    transition:
      max-height 180ms ease,
      opacity 180ms ease,
      transform 180ms ease;
  }

  .field-error-enter-from,
  .field-error-leave-to {
    max-height: 0;
    opacity: 0;
    transform: translateY(-0.2rem);
  }

  .field-error-enter-to,
  .field-error-leave-from {
    max-height: 1.2rem;
    opacity: 1;
    transform: translateY(0);
  }

  .auth-form__field-error {
    display: block;
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

  @media (min-width: 42rem) {
    .auth-form__extra--names {
      column-gap: var(--s-app-space-3);
      display: grid;
      grid-template-columns: 1fr 1fr;
      row-gap: var(--s-app-space-2);
    }
  }
</style>

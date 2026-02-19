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
        <SelectButton
          v-model="mode"
          :options="[
            { label: $t('auth.login'), value: 'login' },
            { label: $t('auth.register'), value: 'register' },
          ]"
          option-label="label"
          option-value="value"
          class="auth-form__mode"
        />

        <Form v-slot="$form" class="auth-form__fields">
          <Transition name="auth-form-expand">
            <div v-if="mode === 'register'" class="auth-form__extra">
              <FormField name="firstName" class="auth-form__field">
                <Typography variant="label" class="auth-form__label" for="auth-first-name">
                  {{ $t("auth.firstName") }}
                </Typography>
                <InputText
                  id="auth-first-name"
                  class="auth-form__control"
                  type="text"
                  name="firstName"
                  :placeholder="$t('auth.firstName')"
                />
              </FormField>
              <FormField name="lastName" class="auth-form__field">
                <Typography variant="label" class="auth-form__label" for="auth-last-name">
                  {{ $t("auth.lastName") }}
                </Typography>
                <InputText
                  id="auth-last-name"
                  class="auth-form__control"
                  type="text"
                  name="lastName"
                  :placeholder="$t('auth.lastName')"
                />
              </FormField>
            </div>
          </Transition>

          <FormField name="email" class="auth-form__field">
            <Typography variant="label" class="auth-form__label" for="auth-email">
              {{ $t("auth.email") }}
            </Typography>
            <InputText
              id="auth-email"
              class="auth-form__control"
              type="email"
              name="email"
              :placeholder="$t('auth.emailPlaceholder')"
            />
          </FormField>
          <FormField name="password" class="auth-form__field">
            <Typography variant="label" class="auth-form__label" for="auth-password">
              {{ $t("auth.password") }}
            </Typography>
            <Password
              id="auth-password"
              class="auth-form__control"
              name="password"
              :feedback="false"
              fluid
              :placeholder="$t('auth.password')"
            />
          </FormField>

          <Transition name="auth-form-expand">
            <div v-if="mode === 'register'" class="auth-form__extra auth-form__extra--compact">
              <FormField name="confirmPassword" class="auth-form__field">
                <Typography variant="label" class="auth-form__label" for="auth-confirm-password">
                  {{ $t("auth.confirmPassword") }}
                </Typography>
                <Password
                  id="auth-confirm-password"
                  class="auth-form__control"
                  name="confirmPassword"
                  :feedback="false"
                  fluid
                  :placeholder="$t('auth.confirmPassword')"
                />
              </FormField>
            </div>
          </Transition>

          <Button
            fluid
            type="submit"
            class="auth-form__submit"
            :label="$t(`auth.${mode}Submit`)"
            :disabled="!$form.valid"
          />
        </Form>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
  import { Form, FormField } from "@primevue/forms";
  import { ref } from "vue";

  type AuthMode = "login" | "register";

  const mode = ref<AuthMode>("login");
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
    width: 100%;
  }

  .auth-form__content,
  .auth-form__fields,
  .auth-form__extra {
    @include layout.stack(var(--s-app-space-4));
  }
</style>

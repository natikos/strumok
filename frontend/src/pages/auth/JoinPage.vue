<template>
  <AuthLayout class="join-page">
    <Card class="join-card">
      <template #title>
        <div class="join-card__header">
          <Typography variant="h1">{{ $t("auth.joinTitle") }}</Typography>
          <Typography variant="subtitle">{{ $t("auth.joinSubtitle") }}</Typography>
        </div>
      </template>

      <template #content>
        <div class="join-card__content">
          <Form
            v-slot="$form"
            class="join-card__form"
            :resolver="resolver"
            @submit="handleSubmit"
          >
            <FormFieldControl
              id="join-first-name"
              name="first_name"
              autocomplete="given-name"
              label-key="auth.firstName"
              placeholder-key="auth.firstName"
              :disabled="isSubmitting"
            />
            <FormFieldControl
              id="join-last-name"
              name="last_name"
              autocomplete="family-name"
              label-key="auth.lastName"
              placeholder-key="auth.lastName"
              :disabled="isSubmitting"
            />
            <FormFieldControl
              id="join-email"
              name="email"
              type="email"
              autocomplete="username"
              label-key="auth.email"
              placeholder-key="auth.emailPlaceholder"
              :disabled="isSubmitting"
            />
            <FormFieldControl
              id="join-password"
              name="password"
              type="password"
              :input-props="{ autocomplete: 'new-password', name: 'password' }"
              label-key="auth.password"
              placeholder-key="auth.password"
              :disabled="isSubmitting"
            />

            <FormField v-slot="$field" name="household_id" class="join-card__plot">
              <Typography variant="label" for="join-household">
                {{ $t("auth.joinPlot") }}
              </Typography>

              <Skeleton v-if="isLoading" class="join-card__plot-skeleton" height="2.75rem" />

              <Message v-else-if="loadFailed" severity="error" role="alert">
                {{ $t("auth.joinLoadFailed") }}
                <Button text :label="$t('errors.retry')" @click="loadHouseholds" />
              </Message>

              <Message v-else-if="households.length === 0" severity="warn" role="status">
                {{ $t("auth.joinNoPlots") }}
              </Message>

              <template v-else>
                <Select
                  input-id="join-household"
                  name="household_id"
                  fluid
                  filter
                  option-label="name"
                  option-value="id"
                  :options="households"
                  :placeholder="$t('auth.joinPlotPlaceholder')"
                  :disabled="isSubmitting"
                  :invalid="$field.invalid"
                />
                <Typography v-if="$field.invalid && $field.error?.message" variant="caption">
                  {{ $t($field.error.message) }}
                </Typography>
              </template>
            </FormField>

            <Button
              fluid
              type="submit"
              :label="$t('auth.joinSubmit')"
              :disabled="isSubmitting || isLoading || !isComplete($form)"
              :loading="isSubmitting"
            />
          </Form>

          <p class="join-card__login">
            {{ $t("auth.joinHaveAccount") }}
            <RouterLink :to="ROUTES.auth">{{ $t("auth.login") }}</RouterLink>
          </p>
        </div>
      </template>
    </Card>
  </AuthLayout>
</template>

<script setup lang="ts">
  import { Form, FormField } from "@primevue/forms";
  import { zodResolver } from "@primevue/forms/resolvers/zod";
  import { onMounted, ref } from "vue";
  import { useRouter } from "vue-router";
  import { z } from "zod";

  import type { FormSubmitEvent } from "@primevue/forms/form";
  import { ApiError, getJoinableHouseholds, joinAsResident } from "@shared/api/auth";
  import type { HouseholdSummary } from "@shared/api/auth";
  import FormFieldControl from "@shared/FormFieldControl.vue";
  import { ROUTES } from "@shared/routing/routes";

  const router = useRouter();

  const households = ref<HouseholdSummary[]>([]);
  const isLoading = ref(true);
  const loadFailed = ref(false);
  const isSubmitting = ref(false);

  const text = () => z.string({ error: "auth.requiredField" }).trim();

  const schema = z.object({
    first_name: text().min(2, "auth.nameMinLength"),
    last_name: text().min(2, "auth.nameMinLength"),
    email: text().pipe(z.email("auth.invalidEmail")),
    password: z.string({ error: "auth.requiredField" }).min(8, "auth.passwordMinLength"),
    household_id: z.number({ error: "auth.joinPlotRequired" }),
  });
  const resolver = zodResolver(schema);

  // A fresh form reports `valid` until something is touched, so the submit
  // button checks the current values against the schema instead.
  function isComplete($form: Record<string, { value?: unknown } | undefined>): boolean {
    const values = Object.fromEntries(
      Object.keys(schema.shape).map((name) => [name, $form[name]?.value])
    );
    return schema.safeParse(values).success;
  }

  async function loadHouseholds(): Promise<void> {
    isLoading.value = true;
    loadFailed.value = false;

    try {
      households.value = await getJoinableHouseholds();
    } catch {
      loadFailed.value = true;
    } finally {
      isLoading.value = false;
    }
  }

  async function handleSubmit(event: FormSubmitEvent): Promise<void> {
    const parsed = schema.safeParse(event.values);

    if (!event.valid || !parsed.success) {
      return;
    }

    isSubmitting.value = true;

    try {
      const me = await joinAsResident(parsed.data);
      await router.push(me.email_verified ? ROUTES.root : ROUTES.verifyEmail);
    } catch (error: unknown) {
      // The global error toast reports the failure. A plot someone else just
      // took is gone from the list, so refresh it.
      if (error instanceof ApiError && error.status === 409) {
        await loadHouseholds();
      }
    } finally {
      isSubmitting.value = false;
    }
  }

  onMounted(loadHouseholds);
</script>

<style scoped lang="scss">
  .join-card {
    width: min(100%, 31.25rem);

    &__header,
    &__content,
    &__form {
      @include layout.stack(var(--s-app-space-3));
      min-width: 0;
    }

    &__plot {
      @include layout.stack(var(--s-app-space-1));
      min-width: 0;
    }

    &__login {
      text-align: center;

      a {
        color: var(--p-primary-color);
      }
    }
  }
</style>

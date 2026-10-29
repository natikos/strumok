<template>
  <div class="settings-card">
    <div class="settings-row">
      <div class="settings-row__info">
        <Key class="settings-row__icon" />
        <div>
          <span class="settings-row__label">{{ t("settings.account.password") }}</span>
          <span class="settings-row__hint">{{ t("settings.account.passwordHint") }}</span>
        </div>
      </div>
      <Button
        v-if="openForm !== 'password'"
        :label="t('settings.account.change')"
        severity="secondary"
        size="small"
        @click="open('password')"
      />
    </div>

    <form
      v-if="openForm === 'password'"
      class="account-form"
      @submit.prevent="handleChangePassword"
    >
      <Password
        v-model="currentPassword"
        autocomplete="current-password"
        :feedback="false"
        fluid
        :placeholder="t('settings.account.currentPassword')"
        toggle-mask
      />
      <Password
        v-model="newPassword"
        autocomplete="new-password"
        :feedback="false"
        fluid
        :placeholder="t('settings.account.newPassword')"
        toggle-mask
      />
      <Message v-if="throttled" severity="error" size="small">
        {{ t("settings.account.tryAgainIn", { timer: cooldownTimer }) }}
      </Message>
      <div class="account-form__actions">
        <Button
          :disabled="submitDisabled || newPassword.length < 8"
          :label="t('settings.account.savePassword')"
          type="submit"
        />
        <Button
          :label="t('settings.account.cancel')"
          severity="secondary"
          type="button"
          variant="text"
          @click="close"
        />
      </div>
    </form>

    <Message v-if="notice" class="account-notice" severity="success" size="small">
      {{ notice }}
    </Message>

    <div class="settings-row">
      <div class="settings-row__info">
        <Envelope class="settings-row__icon" />
        <div>
          <span class="settings-row__label">{{ t("settings.account.email") }}</span>
          <span class="settings-row__hint">{{ currentEmail }}</span>
        </div>
      </div>
      <Button
        v-if="openForm !== 'email'"
        :label="t('settings.account.change')"
        severity="secondary"
        size="small"
        @click="open('email')"
      />
    </div>

    <form v-if="openForm === 'email'" class="account-form" @submit.prevent="handleChangeEmail">
      <InputText
        v-model="newEmail"
        autocomplete="email"
        fluid
        :placeholder="t('settings.account.newEmail')"
        type="email"
      />
      <Password
        v-model="currentPassword"
        autocomplete="current-password"
        :feedback="false"
        fluid
        :placeholder="t('settings.account.currentPassword')"
        toggle-mask
      />
      <Message v-if="throttled" severity="error" size="small">
        {{ t("settings.account.tryAgainIn", { timer: cooldownTimer }) }}
      </Message>
      <div class="account-form__actions">
        <Button
          :disabled="submitDisabled || !newEmail"
          :label="t('settings.account.sendEmailLink')"
          type="submit"
        />
        <Button
          :label="t('settings.account.cancel')"
          severity="secondary"
          type="button"
          variant="text"
          @click="close"
        />
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
  import { Envelope, Key } from "@primeicons/vue";
  import { computed, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { ApiError, changePassword, requestEmailChange } from "@shared/api/auth";
  import { useCountdown } from "@shared/composables/useCountdown";

  defineProps<{ currentEmail: string }>();

  const { t } = useI18n();
  const {
    formatted: cooldownTimer,
    seconds: cooldownSeconds,
    start: startCooldown,
  } = useCountdown();

  const openForm = ref<"email" | "password" | null>(null);
  const currentPassword = ref("");
  const newPassword = ref("");
  const newEmail = ref("");
  const isSubmitting = ref(false);
  const notice = ref("");

  const throttled = computed(() => cooldownSeconds.value > 0);
  const submitDisabled = computed(
    () => isSubmitting.value || throttled.value || currentPassword.value.length === 0
  );

  function open(form: "email" | "password"): void {
    openForm.value = form;
    notice.value = "";
  }

  function close(): void {
    openForm.value = null;
    currentPassword.value = "";
    newPassword.value = "";
    newEmail.value = "";
  }

  // Wrong password / taken email surface through the global error toast; only
  // the throttle has inline UI (a countdown).
  async function submit(action: () => Promise<void>, successMessage: string): Promise<void> {
    isSubmitting.value = true;

    try {
      await action();
      close();
      notice.value = successMessage;
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 429) {
        startCooldown(error.retryAfterSeconds ?? 60);
      }
    } finally {
      isSubmitting.value = false;
    }
  }

  async function handleChangePassword(): Promise<void> {
    await submit(
      () =>
        changePassword({
          current_password: currentPassword.value,
          new_password: newPassword.value,
        }),
      t("settings.account.passwordChanged")
    );
  }

  async function handleChangeEmail(): Promise<void> {
    const email = newEmail.value.trim();

    await submit(
      () => requestEmailChange({ current_password: currentPassword.value, new_email: email }),
      t("settings.account.emailLinkSent", { email })
    );
  }
</script>

<style scoped lang="scss">
  .account-form {
    @include layout.stack(var(--s-app-space-3));
    border-top: 1px solid var(--s-content-border-color);
    padding: var(--s-app-space-4);

    &__actions {
      @include layout.row(var(--s-app-space-2), center);
      flex-wrap: wrap;
    }
  }

  .account-notice {
    margin: 0 var(--s-app-space-4) var(--s-app-space-4);
  }
</style>

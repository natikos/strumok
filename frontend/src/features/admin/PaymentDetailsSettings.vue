<template>
  <form class="payment-details" @submit.prevent="save">
    <p class="payment-details__hint">{{ t("admin.paymentDetails.hint") }}</p>

    <div class="payment-details__field">
      <label for="payment-iban">{{ t("admin.paymentDetails.iban") }}</label>
      <InputText
        id="payment-iban"
        v-model="iban"
        autocomplete="off"
        inputmode="text"
        :disabled="isBusy"
      />
    </div>

    <div class="payment-details__field">
      <label for="payment-recipient">{{ t("admin.paymentDetails.recipient") }}</label>
      <InputText id="payment-recipient" v-model="recipient" autocomplete="off" :disabled="isBusy" />
    </div>

    <Button
      type="submit"
      :label="t('admin.paymentDetails.save')"
      :loading="isBusy"
      :disabled="!iban.trim() || !recipient.trim()"
    />
    <p v-if="isSaved" class="payment-details__saved" role="status">
      {{ t("admin.paymentDetails.saved") }}
    </p>
  </form>
</template>

<script setup lang="ts">
  import { onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { getAdminPaymentDetails, putAdminPaymentDetails } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";

  const { t } = useI18n();

  const iban = ref("");
  const recipient = ref("");
  const isBusy = ref(false);
  const isSaved = ref(false);

  async function load(): Promise<void> {
    const details = await getAdminPaymentDetails();
    iban.value = details?.iban ?? "";
    recipient.value = details?.recipient_name ?? "";
  }

  async function save(): Promise<void> {
    isBusy.value = true;
    isSaved.value = false;

    try {
      const saved = await putAdminPaymentDetails({
        iban: iban.value,
        recipient_name: recipient.value,
      });
      iban.value = saved.iban;
      recipient.value = saved.recipient_name;
      isSaved.value = true;
    } catch (error: unknown) {
      // ApiError is toasted globally (errors.invalidIban); anything else is a bug.
      if (!(error instanceof ApiError)) {
        throw error;
      }
    } finally {
      isBusy.value = false;
    }
  }

  onMounted(load);
</script>

<style scoped lang="scss">
  .payment-details {
    display: grid;
    gap: var(--s-app-space-3);
    min-width: 0;

    &__hint {
      margin: 0;
    }

    &__field {
      display: grid;
      gap: var(--s-app-space-1);
      min-width: 0;
    }
  }
</style>

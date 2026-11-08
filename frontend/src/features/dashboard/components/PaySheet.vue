<template>
  <Dialog
    v-model:visible="visible"
    modal
    class="pay-sheet-dialog"
    :header="t('balance.payTitle')"
  >
    <p class="pay-sheet__hint">{{ t("balance.payHint") }}</p>

    <a class="pay-sheet__bank p-button" :href="bankLink" target="_blank" rel="noopener">
      {{ t("balance.payOpenBank") }}
    </a>
    <Button
      type="button"
      severity="secondary"
      class="pay-sheet__link"
      :label="copied === 'link' ? t('balance.payCopied') : t('balance.payCopyLink')"
      @click="copy('link', detailsText)"
    />

    <dl class="pay-sheet__fields">
      <div v-for="field in fields" :key="field.key" class="pay-sheet__field">
        <dt class="pay-sheet__label">{{ field.label }}</dt>
        <dd class="pay-sheet__row">
          <span class="pay-sheet__value" data-testid="pay-value">{{ field.value }}</span>
          <Button
            type="button"
            size="small"
            severity="secondary"
            :label="copied === field.key ? t('balance.payCopied') : t('balance.payCopy')"
            :aria-label="`${t('balance.payCopy')}: ${field.label}`"
            @click="copy(field.key, field.value)"
          />
        </dd>
      </div>
    </dl>

    <p v-if="copyFailed" class="pay-sheet__error" role="alert">
      {{ t("balance.payCopyFailed") }}
    </p>
  </Dialog>
</template>

<script setup lang="ts">
  import { computed, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { bankPaymentLink } from "@shared/utils/bankLink";

  const props = defineProps<{
    amount: string;
    iban: string;
    recipient: string;
    edrpou?: string | null | undefined;
    comment: string;
  }>();

  const visible = defineModel<boolean>("visible", { required: true });

  const { t } = useI18n();

  const bankLink = computed(() =>
    bankPaymentLink({
      recipient: props.recipient,
      iban: props.iban,
      edrpou: props.edrpou,
      amount: props.amount,
      purpose: props.comment,
    })
  );

  // Labelled plain text: pasted into a bank app (e.g. monobank) it can pick the
  // IBAN and other details out, unlike a bare link.
  const detailsText = computed(() =>
    fields.value.map((field) => `${field.label}: ${field.value}`).join("\n")
  );

  const copied = ref<string | null>(null);
  const copyFailed = ref(false);

  const fields = computed(() => [
    { key: "amount", label: t("balance.payAmount"), value: props.amount },
    { key: "iban", label: t("balance.payIban"), value: props.iban },
    { key: "recipient", label: t("balance.payRecipient"), value: props.recipient },
    ...(props.edrpou
      ? [{ key: "edrpou", label: t("balance.payEdrpou"), value: props.edrpou }]
      : []),
    { key: "comment", label: t("balance.payComment"), value: props.comment },
  ]);

  async function copy(key: string, value: string): Promise<void> {
    copyFailed.value = false;

    try {
      await navigator.clipboard.writeText(value);
      copied.value = key;
    } catch {
      // No Clipboard API (insecure origin, old WebView): the value is shown as
      // selectable text, so tell the resident to select it by hand.
      copied.value = null;
      copyFailed.value = true;
    }
  }
</script>

<style lang="scss">
  // The dialog is teleported to <body>, so this block can't be scoped. Full
  // screen at 360px; a centred card from "sm" up.
  .pay-sheet-dialog {
    border-radius: 0;
    height: 100%;
    max-height: 100%;
    width: 100vw;

    @include layout.respond-to("sm") {
      border-radius: var(--s-app-radius-md);
      height: auto;
      max-height: 90%;
      width: 28rem;
    }
  }
</style>

<style scoped lang="scss">
  .pay-sheet {
    &__hint {
      margin: 0 0 var(--s-app-space-4);
    }

    &__bank,
    &__link {
      justify-content: center;
      margin-bottom: var(--s-app-space-3);
      min-height: 44px;
      text-decoration: none;
      width: 100%;
    }

    &__fields {
      display: grid;
      gap: var(--s-app-space-3);
      margin: 0;
    }

    &__field {
      min-width: 0;
    }

    &__label {
      font-size: 0.8rem;
      opacity: 0.7;
    }

    &__row {
      @include layout.row(var(--s-app-space-3), center);
      margin: 0;
    }

    &__value {
      flex: 1;
      min-width: 0;
      overflow-wrap: anywhere;
      user-select: all;
    }

    &__error {
      color: var(--s-red-500);
      margin: var(--s-app-space-3) 0 0;
    }
  }
</style>

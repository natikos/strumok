<template>
  <section class="inbox" :aria-label="t('admin.bank.inbox.title')">
    <div class="inbox__head">
      <h3 class="inbox__title">{{ t("admin.bank.inbox.title") }}</h3>
      <Button
        size="small"
        severity="secondary"
        :label="t('admin.bank.inbox.check')"
        :loading="isChecking"
        @click="check"
      />
    </div>

    <ErrorState v-if="error" :message-key="error" @retry="load" />

    <p v-else-if="!isLoading && !fetches.length" class="inbox__empty">
      {{ t("admin.bank.inbox.empty") }}
    </p>

    <ul v-else class="inbox__list">
      <li
        v-for="fetch in fetches"
        :key="fetch.id"
        class="inbox__row"
        :class="{ 'inbox__row--rejected': fetch.status === 'rejected' }"
      >
        <span class="inbox__when">{{ format(new Date(fetch.fetched_at), "dd.MM HH:mm") }}</span>
        <span class="inbox__status">{{ t(`admin.bank.inbox.status.${fetch.status}`) }}</span>
        <span v-if="fetch.reason" class="inbox__reason">{{ reasonText(fetch.reason) }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
  import { format } from "date-fns";
  import { useToast } from "primevue/usetoast";
  import { onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { checkBankInbox, type InboxFetchOut, listInboxFetches } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";

  const emit = defineEmits<{ imported: [] }>();

  const i18n = useI18n();
  const { t } = i18n;
  const toast = useToast();

  const fetches = ref<InboxFetchOut[]>([]);
  const error = ref<string | null>(null);
  const isLoading = ref(true);
  const isChecking = ref(false);

  function reasonText(reason: string): string {
    for (const key of [`admin.bank.inbox.reason.${reason}`, `errors.${reason}`]) {
      if (i18n.te(key)) {
        return t(key);
      }
    }

    return reason;
  }

  async function load(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      fetches.value = await listInboxFetches();
    } catch {
      error.value = "errors.requestFailed";
    } finally {
      isLoading.value = false;
    }
  }

  async function check(): Promise<void> {
    isChecking.value = true;

    try {
      const result = await checkBankInbox();
      toast.add({
        life: 6000,
        severity: result.rejected > 0 ? "warn" : "success",
        summary: t("admin.bank.inbox.checked", {
          received: result.received,
          imported: result.imported,
          rejected: result.rejected,
        }),
      });
      if (result.imported > 0) {
        emit("imported");
      }
    } catch (caught: unknown) {
      // ApiError (inboxNotConfigured, inboxUnavailable) is toasted globally.
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
    } finally {
      isChecking.value = false;
      await load();
    }
  }

  onMounted(load);
</script>

<style scoped lang="scss">
  .inbox {
    display: grid;
    gap: var(--s-app-space-2);
    min-width: 0;

    &__head {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: var(--s-app-space-2);
      justify-content: space-between;
    }

    &__title,
    &__empty {
      margin: 0;
    }

    &__title {
      font-size: 1rem;
    }

    &__list {
      display: grid;
      gap: var(--s-app-space-1);
      list-style: none;
      margin: 0;
      padding: 0;
    }

    &__row {
      display: flex;
      flex-wrap: wrap;
      gap: var(--s-app-space-2);
      min-width: 0;
      overflow-wrap: anywhere;

      &--rejected {
        color: var(--s-red-500);
      }
    }
  }
</style>

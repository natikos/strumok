<template>
  <div class="residents">
    <InputText
      v-model="filter"
      class="residents__filter"
      fluid
      :placeholder="t('admin.users.filter')"
      :aria-label="t('admin.users.filter')"
    />

    <div class="residents__invite">
      <Button v-if="!showInvite" :label="t('admin.users.invite')" @click="openInvite" />

      <form v-else class="residents__invite-form" @submit.prevent="submitInvite">
        <InputText
          v-model="invite.first_name"
          fluid
          :placeholder="t('admin.users.inviteFirstName')"
          :aria-label="t('admin.users.inviteFirstName')"
        />
        <InputText
          v-model="invite.last_name"
          fluid
          :placeholder="t('admin.users.inviteLastName')"
          :aria-label="t('admin.users.inviteLastName')"
        />
        <InputText
          v-model="invite.email"
          fluid
          type="email"
          :placeholder="t('admin.users.inviteEmail')"
          :aria-label="t('admin.users.inviteEmail')"
        />
        <Select
          v-model="invite.language"
          fluid
          :options="LANGUAGES"
          option-label="label"
          option-value="value"
          :aria-label="t('admin.users.inviteLanguage')"
        />
        <Select
          v-model="invite.household_id"
          fluid
          :options="freeHouseholds"
          option-label="name"
          option-value="id"
          show-clear
          :placeholder="t('admin.users.inviteHousehold')"
          :aria-label="t('admin.users.inviteHousehold')"
        />
        <div class="residents__invite-actions">
          <Button
            type="submit"
            :disabled="isInviting || !canInvite"
            :loading="isInviting"
            :label="t('admin.users.inviteSend')"
          />
          <Button
            type="button"
            severity="secondary"
            variant="text"
            :label="t('admin.users.cancel')"
            @click="showInvite = false"
          />
        </div>
      </form>

      <Message
        v-if="inviteResult"
        class="residents__result"
        :severity="inviteResult.email_sent ? 'success' : 'warn'"
      >
        <div class="residents__result-body">
          <span>{{
            inviteResult.email_sent
              ? t("admin.users.inviteSent", { email: inviteResult.user.email })
              : t("admin.users.inviteNotSent")
          }}</span>
          <Button
            size="small"
            severity="secondary"
            :label="t('admin.users.copyLink')"
            @click="copyLink(inviteResult.invite_link)"
          />
        </div>
      </Message>
    </div>

    <ErrorState v-if="error" :message-key="error" @retry="load" />

    <div class="residents__card">
      <div class="residents__scroll">
        <table class="residents__table">
          <thead>
            <tr>
              <th scope="col">{{ t("admin.users.name") }}</th>
              <th scope="col">{{ t("admin.users.email") }}</th>
              <th scope="col">{{ t("admin.users.households") }}</th>
              <th scope="col">{{ t("admin.users.status") }}</th>
              <th scope="col">{{ t("admin.users.role") }}</th>
              <th scope="col">
                <span class="sr-only">{{ t("admin.users.actions", { name: "" }) }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in visibleUsers" :key="user.id">
              <th scope="row">{{ fullName(user) }}</th>
              <td>{{ user.email }}</td>
              <td>{{ user.household_count }}</td>
              <td>
                <span
                  class="residents__pill"
                  :class="user.is_active ? 'residents__pill--ok' : 'residents__pill--off'"
                >
                  {{
                    user.invite_pending
                      ? t("admin.users.invitePending")
                      : user.is_active
                        ? t("admin.users.active")
                        : t("admin.users.inactive")
                  }}
                </span>
              </td>
              <td>
                <span class="residents__pill">{{
                  user.is_admin ? t("admin.users.admin") : t("admin.users.resident")
                }}</span>
              </td>
              <td>
                <Button
                  icon="pi pi-ellipsis-v"
                  severity="secondary"
                  variant="text"
                  :aria-label="t('admin.users.actions', { name: fullName(user) })"
                  @click="openMenu($event, user)"
                />
              </td>
            </tr>
            <tr v-if="!isLoading && visibleUsers.length === 0">
              <td class="residents__empty" colspan="6">{{ t("admin.users.empty") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Menu ref="menu" :model="menuItems" popup />
  </div>
</template>

<script setup lang="ts">
  import { useConfirm } from "primevue/useconfirm";
  import { useToast } from "primevue/usetoast";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    type AdminHouseholdOut,
    type AdminInviteOut,
    type AdminUserOut,
    inviteAdminUser,
    listAdminHouseholds,
    listAdminUsers,
    resendAdminInvite,
    updateAdminUser,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";

  const { t } = useI18n();
  const confirm = useConfirm();
  const toast = useToast();

  const LANGUAGES = [
    { label: "Українська", value: "ua" as const },
    { label: "English", value: "en" as const },
  ];

  const households = ref<AdminHouseholdOut[]>([]);
  const showInvite = ref(false);
  const isInviting = ref(false);
  const inviteResult = ref<AdminInviteOut | null>(null);
  const invite = ref<{
    email: string;
    first_name: string;
    household_id: number | null;
    language: "en" | "ua";
    last_name: string;
  }>({ email: "", first_name: "", household_id: null, language: "ua", last_name: "" });

  const freeHouseholds = computed(() =>
    households.value.filter((household) => household.is_active && household.user_id === null)
  );
  const canInvite = computed(
    () =>
      invite.value.first_name.trim().length >= 2 &&
      invite.value.last_name.trim().length >= 2 &&
      invite.value.email.includes("@")
  );

  async function openInvite(): Promise<void> {
    showInvite.value = true;
    inviteResult.value = null;
    households.value = await listAdminHouseholds();
  }

  async function submitInvite(): Promise<void> {
    isInviting.value = true;

    try {
      const { household_id: householdId, ...rest } = invite.value;
      inviteResult.value = await inviteAdminUser({
        ...rest,
        ...(householdId !== null ? { household_id: householdId } : {}),
      });
      showInvite.value = false;
      invite.value = {
        email: "",
        first_name: "",
        household_id: null,
        language: "ua",
        last_name: "",
      };
      await load();
    } catch (caught: unknown) {
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
    } finally {
      isInviting.value = false;
    }
  }

  async function resend(user: AdminUserOut): Promise<void> {
    try {
      inviteResult.value = await resendAdminInvite(user.id);
    } catch (caught: unknown) {
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
    }
  }

  async function copyLink(link: string): Promise<void> {
    await navigator.clipboard.writeText(link);
    toast.add({ detail: t("admin.users.linkCopied"), life: 3000, severity: "success" });
  }

  const users = ref<AdminUserOut[]>([]);
  const filter = ref("");
  const isLoading = ref(true);
  const error = ref<string | null>(null);
  const menu = ref<{ toggle: (event: Event) => void } | null>(null);
  const menuUser = ref<AdminUserOut | null>(null);

  const visibleUsers = computed(() => {
    const needle = filter.value.trim().toLowerCase();

    if (!needle) {
      return users.value;
    }

    return users.value.filter((user) =>
      `${fullName(user)} ${user.email}`.toLowerCase().includes(needle)
    );
  });

  const menuItems = computed(() => {
    const user = menuUser.value;

    if (!user) {
      return [];
    }

    const items = user.invite_pending
      ? [{ command: () => void resend(user), label: t("admin.users.sendInvite") }]
      : [];

    return [
      ...items,
      user.is_active
        ? { command: () => askDeactivate(user), label: t("admin.users.deactivate") }
        : { command: () => askReactivate(user), label: t("admin.users.reactivate") },
      user.is_admin
        ? { command: () => askRoleChange(user, false), label: t("admin.users.revokeAdmin") }
        : { command: () => askRoleChange(user, true), label: t("admin.users.grantAdmin") },
    ];
  });

  function fullName(user: AdminUserOut): string {
    return `${user.first_name} ${user.last_name}`;
  }

  function openMenu(event: Event, user: AdminUserOut): void {
    menuUser.value = user;
    menu.value?.toggle(event);
  }

  async function load(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      users.value = await listAdminUsers();
    } catch {
      error.value = "errors.requestFailed";
    } finally {
      isLoading.value = false;
    }
  }

  async function apply(
    user: AdminUserOut,
    payload: Parameters<typeof updateAdminUser>[1]
  ): Promise<void> {
    try {
      const updated = await updateAdminUser(user.id, payload);
      users.value = users.value.map((item) => (item.id === updated.id ? updated : item));
    } catch (caught: unknown) {
      if (!(caught instanceof ApiError)) {
        throw caught;
      }
      // The global error toast reports the failure.
    }
  }

  function ask(options: { body: string; header: string; onAccept: () => void }): void {
    confirm.require({
      accept: options.onAccept,
      acceptLabel: t("admin.users.confirm"),
      header: options.header,
      message: options.body,
      rejectLabel: t("admin.users.cancel"),
    });
  }

  function askDeactivate(user: AdminUserOut): void {
    const owns = user.household_count > 0;

    ask({
      body: owns
        ? t("admin.users.deactivateOwnerBody", { count: user.household_count })
        : t("admin.users.deactivateBody"),
      header: t("admin.users.deactivateTitle", { name: fullName(user) }),
      onAccept: () =>
        void apply(user, { is_active: false, ...(owns ? { unassign_households: true } : {}) }),
    });
  }

  function askReactivate(user: AdminUserOut): void {
    ask({
      body: t("admin.users.reactivateBody"),
      header: t("admin.users.reactivateTitle", { name: fullName(user) }),
      onAccept: () => void apply(user, { is_active: true }),
    });
  }

  function askRoleChange(user: AdminUserOut, grant: boolean): void {
    const name = fullName(user);

    ask({
      body: grant ? t("admin.users.grantBody", { name }) : t("admin.users.revokeBody"),
      header: grant
        ? t("admin.users.grantTitle", { name })
        : t("admin.users.revokeTitle", { name }),
      onAccept: () => void apply(user, { is_admin: grant }),
    });
  }

  onMounted(load);
</script>

<style scoped lang="scss">
  .residents {
    @include layout.stack(var(--s-app-space-4));
    min-width: 0;

    &__invite,
    &__invite-form {
      @include layout.stack(var(--s-app-space-3));
      min-width: 0;
    }

    &__invite-actions,
    &__result-body {
      @include layout.row(var(--s-app-space-2), center);
      flex-wrap: wrap;
    }

    &__card {
      background: var(--s-content-background);
      border: 1px solid var(--s-content-border-color);
      border-radius: var(--s-app-radius-md);
      overflow: hidden;
    }

    &__scroll {
      overflow-x: auto;
    }

    &__table {
      border-collapse: collapse;
      font-size: 0.9rem;
      min-width: 40rem;
      width: 100%;

      th,
      td {
        padding: var(--s-app-space-3);
        text-align: left;
        white-space: nowrap;
      }

      tbody tr + tr {
        border-top: 1px solid var(--s-content-border-color);
      }
    }

    &__pill {
      border: 1px solid var(--s-content-border-color);
      border-radius: 999px;
      font-size: 0.75rem;
      padding: 0.1rem 0.6rem;

      &--ok {
        color: var(--s-green-500);
      }

      &--off {
        color: var(--s-amber-500);
      }
    }

    &__empty {
      text-align: center !important;
    }
  }

  .sr-only {
    clip: rect(0 0 0 0);
    height: 1px;
    overflow: hidden;
    position: absolute;
    width: 1px;
  }
</style>

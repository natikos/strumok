<template>
  <div class="residents">
    <InputText
      v-model="filter"
      class="residents__filter"
      fluid
      :placeholder="t('admin.users.filter')"
      :aria-label="t('admin.users.filter')"
    />

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
              <th scope="col"><span class="sr-only">{{ t("admin.users.actions", { name: "" }) }}</span></th>
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
                  {{ user.is_active ? t("admin.users.active") : t("admin.users.inactive") }}
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
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import { type AdminUserOut, listAdminUsers, updateAdminUser } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";

  const { t } = useI18n();
  const confirm = useConfirm();

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

    return [
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

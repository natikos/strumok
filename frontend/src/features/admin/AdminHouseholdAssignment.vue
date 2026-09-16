<template>
  <div class="admin-assignment">
    <div class="admin-assignment__field">
      <label class="admin-assignment__label" for="admin-household-select">
        {{ $t("admin.household") }}
      </label>
      <Select
        id="admin-household-select"
        v-model="selectedHouseholdId"
        class="admin-assignment__input"
        :options="householdOptions"
        option-label="label"
        option-value="value"
        :placeholder="$t('admin.householdPlaceholder')"
        :disabled="isLoading"
        show-clear
      />
    </div>

    <div v-if="selectedHouseholdId === null" class="admin-assignment__field">
      <label class="admin-assignment__label" for="admin-household-name">
        {{ $t("admin.newHouseholdName") }}
      </label>
      <InputText
        id="admin-household-name"
        v-model="newHouseholdName"
        class="admin-assignment__input"
        :placeholder="$t('admin.newHouseholdNamePlaceholder')"
        :disabled="isLoading"
      />
    </div>

    <div v-else class="admin-assignment__current-owner">
      {{
        selectedHouseholdOwnerLabel
          ? $t("admin.currentOwner", { owner: selectedHouseholdOwnerLabel })
          : $t("admin.currentOwnerNone")
      }}
    </div>

    <div class="admin-assignment__field">
      <label class="admin-assignment__label" for="admin-user-select">
        {{ $t("admin.assignTo") }}
      </label>
      <Select
        id="admin-user-select"
        v-model="selectedUserId"
        class="admin-assignment__input"
        :options="userOptions"
        option-label="label"
        option-value="value"
        :placeholder="$t('admin.assignToPlaceholder')"
        :disabled="isLoading"
      />
    </div>

    <Button
      class="admin-assignment__submit"
      :label="$t('admin.assign')"
      :disabled="!canSubmit || isLoading"
      :loading="isLoading"
      @click="handleSubmit"
    />
  </div>
</template>

<script setup lang="ts">
  import { useConfirm } from "primevue/useconfirm";
  import { useToast } from "primevue/usetoast";
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import {
    type AdminHouseholdOut,
    type AdminUserSummaryOut,
    assignAdminHouseholdOwner,
    createAdminHousehold,
    listAdminHouseholds,
    listAdminUsers,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";

  const { t } = useI18n();
  const confirm = useConfirm();
  const toast = useToast();

  const users = ref<AdminUserSummaryOut[]>([]);
  const households = ref<AdminHouseholdOut[]>([]);
  const isLoading = ref(false);

  const selectedHouseholdId = ref<number | null>(null);
  const newHouseholdName = ref("");
  const selectedUserId = ref<number | null>(null);

  onMounted(async () => {
    isLoading.value = true;

    try {
      const [loadedUsers, loadedHouseholds] = await Promise.all([
        listAdminUsers(),
        listAdminHouseholds(),
      ]);
      users.value = loadedUsers;
      households.value = loadedHouseholds;
    } finally {
      isLoading.value = false;
    }
  });

  function userLabel(user: AdminUserSummaryOut): string {
    return `${user.first_name} ${user.last_name} (${user.email})`;
  }

  const userOptions = computed(() =>
    users.value.map((user) => ({ label: userLabel(user), value: user.id }))
  );

  const householdOptions = computed(() =>
    households.value.map((household) => ({ label: household.name, value: household.id }))
  );

  const selectedHousehold = computed(() =>
    households.value.find((household) => household.id === selectedHouseholdId.value)
  );

  const selectedHouseholdOwnerLabel = computed(() => {
    const owner = selectedHousehold.value?.owner;
    return owner ? userLabel(owner) : null;
  });

  const canSubmit = computed(() => {
    if (selectedUserId.value === null) {
      return false;
    }

    return selectedHouseholdId.value !== null || newHouseholdName.value.trim().length > 0;
  });

  function resetForm(): void {
    selectedHouseholdId.value = null;
    newHouseholdName.value = "";
    selectedUserId.value = null;
  }

  async function performAssignment(confirmReassignment: boolean): Promise<void> {
    if (selectedUserId.value === null) {
      return;
    }

    isLoading.value = true;

    try {
      let household: AdminHouseholdOut;

      if (selectedHouseholdId.value !== null) {
        household = await assignAdminHouseholdOwner(selectedHouseholdId.value, {
          confirm_reassignment: confirmReassignment,
          user_id: selectedUserId.value,
        });
      } else {
        household = await createAdminHousehold({
          name: newHouseholdName.value.trim(),
          user_id: selectedUserId.value,
        });
        households.value = [...households.value, household];
      }

      const owner = users.value.find((user) => user.id === selectedUserId.value);
      toast.add({
        life: 4000,
        severity: "success",
        summary: t("admin.assignSuccess", {
          household: household.name,
          owner: owner ? userLabel(owner) : "",
        }),
      });

      resetForm();

      const refreshedHouseholds = await listAdminHouseholds();
      households.value = refreshedHouseholds;
    } catch (error: unknown) {
      if (!(error instanceof ApiError)) {
        throw error;
      }
    } finally {
      isLoading.value = false;
    }
  }

  function confirmReassignmentDialog(): void {
    confirm.require({
      accept: () => void performAssignment(true),
      acceptLabel: t("admin.reassignConfirmAccept"),
      header: t("admin.reassignConfirmTitle"),
      message: t("admin.reassignConfirmBody", {
        owner: selectedHouseholdOwnerLabel.value ?? "",
      }),
      rejectLabel: t("admin.reassignConfirmReject"),
    });
  }

  const isReassignment = computed(() => {
    const currentOwnerId = selectedHousehold.value?.user_id;
    return (
      currentOwnerId !== undefined &&
      currentOwnerId !== null &&
      currentOwnerId !== selectedUserId.value
    );
  });

  async function handleSubmit(): Promise<void> {
    if (isReassignment.value) {
      confirmReassignmentDialog();
      return;
    }

    await performAssignment(false);
  }
</script>

<style scoped lang="scss">
  .admin-assignment {
    @include layout.stack(var(--s-app-space-4));
  }

  .admin-assignment__field {
    @include layout.stack(var(--s-app-space-2));
  }

  .admin-assignment__label {
    color: var(--s-content-color);
    font-size: 0.85rem;
    font-weight: 500;
  }

  .admin-assignment__input {
    min-width: 0;
    width: 100%;
  }

  .admin-assignment__current-owner {
    color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    font-size: 0.85rem;
  }

  .admin-assignment__submit {
    width: 100%;
  }
</style>

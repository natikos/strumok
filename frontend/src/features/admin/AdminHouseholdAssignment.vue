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
        :invalid="!!errors.newHouseholdName"
        :disabled="isLoading"
        :aria-invalid="!!errors.newHouseholdName"
        :aria-describedby="errors.newHouseholdName ? 'admin-household-name-error' : undefined"
      />
      <span
        v-if="errors.newHouseholdName"
        id="admin-household-name-error"
        role="alert"
        class="admin-assignment__field-error"
      >
        {{ $t(errors.newHouseholdName) }}
      </span>
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
        :invalid="!!errors.selectedUserId"
        :disabled="isLoading"
        :aria-invalid="!!errors.selectedUserId"
        :aria-describedby="errors.selectedUserId ? 'admin-user-select-error' : undefined"
      />
      <span
        v-if="errors.selectedUserId"
        id="admin-user-select-error"
        role="alert"
        class="admin-assignment__field-error"
      >
        {{ $t(errors.selectedUserId) }}
      </span>
    </div>

    <Button
      class="admin-assignment__submit"
      :label="$t('admin.assign')"
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
  import { z } from "zod";

  import {
    type AdminHouseholdOut,
    type AdminUserSummaryOut,
    assignAdminHouseholdOwner,
    createAdminHousehold,
    listAdminHouseholds,
    listAdminUsers,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";

  interface FieldErrors {
    newHouseholdName?: string;
    selectedUserId?: string;
  }

  const schema = z.object({
    newHouseholdName: z.string().trim().min(1, "admin.newHouseholdNameRequired").optional(),
    selectedUserId: z.number({ error: "admin.assignToRequired" }),
  });

  const { t } = useI18n();
  const confirm = useConfirm();
  const toast = useToast();

  const users = ref<AdminUserSummaryOut[]>([]);
  const households = ref<AdminHouseholdOut[]>([]);
  const isLoading = ref(false);
  const errors = ref<FieldErrors>({});

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

  function resetForm(): void {
    selectedHouseholdId.value = null;
    newHouseholdName.value = "";
    selectedUserId.value = null;
    errors.value = {};
  }

  function validate(): boolean {
    const parsed = schema.safeParse({
      newHouseholdName: newHouseholdName.value.trim() || undefined,
      selectedUserId: selectedUserId.value,
    });

    const next: FieldErrors = {};

    if (!parsed.success) {
      const flat = z.flattenError(parsed.error).fieldErrors;
      if (flat.selectedUserId?.[0]) {
        next.selectedUserId = flat.selectedUserId[0];
      }
    }

    if (selectedHouseholdId.value === null && newHouseholdName.value.trim().length === 0) {
      next.newHouseholdName = "admin.newHouseholdNameRequired";
    }

    errors.value = next;
    return Object.keys(next).length === 0;
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
    if (!validate()) {
      return;
    }

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

  .admin-assignment__field-error {
    font-size: 0.75rem;
    color: var(--s-red-500);
  }

  .admin-assignment__submit {
    width: 100%;
  }
</style>

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
        fluid
        :options="householdOptions"
        option-label="label"
        option-value="value"
        :placeholder="$t('admin.householdPlaceholder')"
        :disabled="isLoading"
        :pt="{ label: { class: 'admin-assignment__select-label' } }"
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
        fluid
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

    <div v-if="selectedHouseholdId === null" class="admin-assignment__starting">
      <div class="admin-assignment__field">
        <label class="admin-assignment__label" for="admin-household-start-day">
          {{ $t("admin.startingDay") }}
        </label>
        <InputNumber
          v-model="startingDay"
          input-id="admin-household-start-day"
          :min="0"
          :min-fraction-digits="2"
          :max-fraction-digits="2"
          fluid
          :disabled="isLoading"
        />
      </div>
      <div class="admin-assignment__field">
        <label class="admin-assignment__label" for="admin-household-start-night">
          {{ $t("admin.startingNight") }}
        </label>
        <InputNumber
          v-model="startingNight"
          input-id="admin-household-start-night"
          :min="0"
          :min-fraction-digits="2"
          :max-fraction-digits="2"
          fluid
          :disabled="isLoading"
        />
      </div>
      <p class="admin-assignment__hint">{{ $t("admin.startingHint") }}</p>
      <span v-if="errors.starting" role="alert" class="admin-assignment__field-error">
        {{ $t(errors.starting) }}
      </span>
    </div>

    <template v-else>
      <div class="admin-assignment__rename">
        <InputText
          v-model="renameValue"
          class="admin-assignment__input"
          :aria-label="$t('admin.renameHousehold')"
          :disabled="isLoading"
        />
        <Button
          :disabled="isLoading || !canRename"
          :label="$t('admin.rename')"
          severity="secondary"
          @click="handleRename"
        />
      </div>

      <div class="admin-assignment__current-owner">
        {{
          selectedHouseholdOwnerLabel
            ? $t("admin.currentOwner", { owner: selectedHouseholdOwnerLabel })
            : $t("admin.currentOwnerNone")
        }}
      </div>
    </template>

    <div class="admin-assignment__field">
      <label class="admin-assignment__label" for="admin-user-select">
        {{ $t("admin.assignTo") }}
      </label>
      <Select
        id="admin-user-select"
        v-model="selectedUserId"
        class="admin-assignment__input"
        fluid
        :options="userOptions"
        option-label="label"
        option-value="value"
        :placeholder="$t('admin.assignToPlaceholder')"
        :invalid="!!errors.selectedUserId"
        :disabled="isLoading"
        :aria-invalid="!!errors.selectedUserId"
        :aria-describedby="errors.selectedUserId ? 'admin-user-select-error' : undefined"
        :pt="{ label: { class: 'admin-assignment__select-label' } }"
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

    <div v-if="isReassignment" class="admin-assignment__starting">
      <p class="admin-assignment__hint">{{ $t("admin.handoverHint") }}</p>
      <div class="admin-assignment__field">
        <label class="admin-assignment__label" for="admin-handover-day">
          {{ $t("admin.handoverDay") }}
        </label>
        <InputNumber
          v-model="handoverDay"
          input-id="admin-handover-day"
          :min="0"
          :min-fraction-digits="2"
          :max-fraction-digits="2"
          fluid
          :disabled="isLoading"
        />
      </div>
      <div class="admin-assignment__field">
        <label class="admin-assignment__label" for="admin-handover-night">
          {{ $t("admin.handoverNight") }}
        </label>
        <InputNumber
          v-model="handoverNight"
          input-id="admin-handover-night"
          :min="0"
          :min-fraction-digits="2"
          :max-fraction-digits="2"
          fluid
          :disabled="isLoading"
        />
      </div>
      <span v-if="errors.handover" role="alert" class="admin-assignment__field-error">
        {{ $t(errors.handover) }}
      </span>
    </div>

    <Button
      class="admin-assignment__submit"
      :label="$t('admin.assign')"
      :loading="isLoading"
      @click="handleSubmit"
    />

    <Button
      v-if="selectedHousehold"
      class="admin-assignment__status"
      :disabled="isLoading"
      :label="selectedHousehold.is_active ? $t('admin.deactivateHousehold') : $t('admin.reactivateHousehold')"
      :severity="selectedHousehold.is_active ? 'danger' : 'secondary'"
      variant="outlined"
      @click="confirmStatusChange"
    />
  </div>
</template>

<script setup lang="ts">
  import { useConfirm } from "primevue/useconfirm";
  import { useToast } from "primevue/usetoast";
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";
  import { z } from "zod";

  import {
    type AdminHouseholdOut,
    type AdminUserSummaryOut,
    assignAdminHouseholdOwner,
    createAdminHousehold,
    listAdminHouseholds,
    listAdminUsers,
    updateAdminHousehold,
  } from "@shared/api/admin";
  import { ApiError } from "@shared/api/client";

  interface FieldErrors {
    newHouseholdName?: string;
    selectedUserId?: string;
    starting?: string;
    handover?: string;
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
  const startingDay = ref<number | null>(null);
  const startingNight = ref<number | null>(null);
  const handoverDay = ref<number | null>(null);
  const handoverNight = ref<number | null>(null);

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
    households.value.map((household) => ({
      label: household.is_active
        ? household.name
        : `${household.name} ${t("admin.inactiveSuffix")}`,
      value: household.id,
    }))
  );

  const selectedHousehold = computed(() =>
    households.value.find((household) => household.id === selectedHouseholdId.value)
  );

  const selectedHouseholdOwnerLabel = computed(() => {
    const owner = selectedHousehold.value?.owner;
    return owner ? userLabel(owner) : null;
  });

  const renameValue = ref("");

  watch(selectedHousehold, (household) => {
    renameValue.value = household?.name ?? "";
  });

  const canRename = computed(() => {
    const trimmed = renameValue.value.trim();
    return trimmed.length > 0 && trimmed !== selectedHousehold.value?.name;
  });

  async function applyHouseholdUpdate(
    payload: Parameters<typeof updateAdminHousehold>[1]
  ): Promise<void> {
    const household = selectedHousehold.value;

    if (!household) {
      return;
    }

    isLoading.value = true;

    try {
      const updated = await updateAdminHousehold(household.id, payload);
      households.value = households.value.map((item) => (item.id === updated.id ? updated : item));
      renameValue.value = updated.name;
    } catch (error: unknown) {
      if (!(error instanceof ApiError)) {
        throw error;
      }
    } finally {
      isLoading.value = false;
    }
  }

  async function handleRename(): Promise<void> {
    await applyHouseholdUpdate({ name: renameValue.value.trim() });
  }

  function confirmStatusChange(): void {
    const household = selectedHousehold.value;

    if (!household) {
      return;
    }

    const deactivating = household.is_active;
    const owner = selectedHouseholdOwnerLabel.value ?? t("admin.currentOwnerNone");

    confirm.require({
      accept: () => void applyHouseholdUpdate({ is_active: !deactivating }),
      acceptLabel: t("admin.users.confirm"),
      header: t(deactivating ? "admin.deactivateHouseholdTitle" : "admin.reactivateHouseholdTitle", {
        name: household.name,
      }),
      message: t(deactivating ? "admin.deactivateHouseholdBody" : "admin.reactivateHouseholdBody", {
        owner,
      }),
      rejectLabel: t("admin.users.cancel"),
    });
  }

  function resetForm(): void {
    selectedHouseholdId.value = null;
    newHouseholdName.value = "";
    selectedUserId.value = null;
    startingDay.value = null;
    startingNight.value = null;
    handoverDay.value = null;
    handoverNight.value = null;
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

    if (
      selectedHouseholdId.value === null &&
      (startingDay.value === null) !== (startingNight.value === null)
    ) {
      next.starting = "admin.startingBoth";
    }

    if (isReassignment.value && (handoverDay.value === null || handoverNight.value === null)) {
      next.handover = "admin.handoverRequired";
    }

    errors.value = next;
    return Object.keys(next).length === 0;
  }

  async function performAssignment(
    confirmReassignment: boolean,
    acknowledgeBalance = false
  ): Promise<void> {
    if (selectedUserId.value === null) {
      return;
    }

    isLoading.value = true;

    try {
      let household: AdminHouseholdOut;

      if (selectedHouseholdId.value !== null) {
        household = await assignAdminHouseholdOwner(selectedHouseholdId.value, {
          acknowledge_balance: acknowledgeBalance,
          confirm_reassignment: confirmReassignment,
          user_id: selectedUserId.value,
          ...(isReassignment.value && handoverDay.value !== null && handoverNight.value !== null
            ? {
                handover_day_meter_value: String(handoverDay.value),
                handover_night_meter_value: String(handoverNight.value),
              }
            : {}),
        });
      } else {
        household = await createAdminHousehold({
          name: newHouseholdName.value.trim(),
          user_id: selectedUserId.value,
          ...(startingDay.value !== null && startingNight.value !== null
            ? {
                starting_day_meter_value: String(startingDay.value),
                starting_night_meter_value: String(startingNight.value),
              }
            : {}),
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

      // The outgoing owner still owes money; it stays with them, but the head
      // must say they know.
      if (error.message === "householdHasOutstandingBalance") {
        confirmBalanceDialog();
      }
    } finally {
      isLoading.value = false;
    }
  }

  function confirmBalanceDialog(): void {
    confirm.require({
      accept: () => void performAssignment(true, true),
      acceptLabel: t("admin.balanceConfirmAccept"),
      header: t("admin.balanceConfirmTitle"),
      message: t("admin.balanceConfirmBody", { owner: selectedHouseholdOwnerLabel.value ?? "" }),
      rejectLabel: t("admin.reassignConfirmReject"),
    });
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
    min-width: 0;
  }

  .admin-assignment__label {
    color: var(--s-content-color);
    font-size: 0.85rem;
    font-weight: 500;
  }

  .admin-assignment__input {
    min-width: 0;
    width: 100%;
    text-overflow: ellipsis;
  }

  .admin-assignment__select-label {
    min-width: 0;
    flex: 1 1 auto;
  }

  .admin-assignment__current-owner {
    color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    font-size: 0.85rem;
  }

  .admin-assignment__field-error {
    font-size: 0.75rem;
    color: var(--s-red-500);
  }

  .admin-assignment__starting {
    @include layout.stack(var(--s-app-space-3));
    min-width: 0;
  }

  .admin-assignment__hint {
    color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    font-size: 0.8rem;
    margin: 0;
  }

  .admin-assignment__rename {
    @include layout.row(var(--s-app-space-2), center);
    min-width: 0;
  }

  .admin-assignment__status {
    width: 100%;
  }

  .admin-assignment__submit {
    width: 100%;
  }
</style>

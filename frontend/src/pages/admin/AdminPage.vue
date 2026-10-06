<template>
  <div class="admin-page">
    <header class="admin-header">
      <h1 class="admin-header__title">{{ $t("admin.title") }}</h1>
    </header>

    <Tabs v-model:value="activeTab" class="admin-tabs">
      <TabList class="admin-tabs__list">
        <Tab value="households">{{ $t("admin.tabHouseholds") }}</Tab>
        <Tab value="rates">{{ $t("admin.tabRates") }}</Tab>
        <Tab value="submissions">{{ $t("admin.tabSubmissions") }}</Tab>
      </TabList>
    </Tabs>

    <div class="admin-body">
      <Tabs v-model:value="activeTab" class="admin-content-tabs">
        <TabPanels>
          <TabPanel value="households">
            <section class="admin-section">
              <h2 class="admin-section__title">{{ $t("admin.householdAssignment") }}</h2>
              <div class="admin-card admin-card--padded">
                <AdminHouseholdAssignment />
              </div>
            </section>
          </TabPanel>

          <TabPanel value="rates">
            <section class="admin-section">
              <h2 class="admin-section__title">{{ $t("admin.electricityRates") }}</h2>
              <div class="admin-card admin-card--padded">
                <ElectricityRatesSettings />
              </div>
            </section>
          </TabPanel>

          <TabPanel value="submissions">
            <section class="admin-section admin-section--wide">
              <div class="admin-section__heading">
                <div>
                  <h2 class="admin-section__title">{{ $t("admin.submissionOverview") }}</h2>
                  <p v-if="dashboard" class="admin-section__period">
                    {{ $t("admin.currentPeriod", { period: dashboard.current_period }) }}
                  </p>
                </div>
                <ProgressSpinner
                  v-if="isLoadingDashboard"
                  class="admin-section__spinner"
                  stroke-width="5"
                />
              </div>

              <div v-if="dashboardError" class="admin-error" role="alert">
                <p class="admin-error__message">{{ $t(dashboardError) }}</p>
                <button class="admin-error__retry" type="button" @click="loadDashboard">
                  {{ $t("errors.requestFailed") }}
                </button>
              </div>

              <div class="admin-card admin-card--table">
                <div v-if="dashboard" class="admin-table-wrap">
                  <table class="admin-table">
                    <thead>
                      <tr>
                        <th scope="col">{{ $t("admin.household") }}</th>
                        <th scope="col">{{ $t("admin.owner") }}</th>
                        <th scope="col">{{ $t("admin.status") }}</th>
                        <th scope="col">{{ $t("admin.latestUsage") }}</th>
                        <th scope="col">{{ $t("admin.latestCharge") }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="household in dashboard.households" :key="household.id">
                        <th scope="row">{{ household.name }}</th>
                        <td>{{ ownerLabel(household) }}</td>
                        <td>
                          <span
                            class="admin-status"
                            :class="`admin-status--${household.submission_status}`"
                          >
                            {{ $t(`admin.${household.submission_status}`) }}
                          </span>
                        </td>
                        <td>{{ formatUsage(household.latest_usage_kwh) }}</td>
                        <td>{{ formatCharge(household.latest_amount_charged_uah) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from "vue";

  import AdminHouseholdAssignment from "@features/admin/AdminHouseholdAssignment.vue";
  import ElectricityRatesSettings from "@features/admin/ElectricityRatesSettings.vue";
  import { type AdminDashboardOut, getAdminDashboard } from "@shared/api/admin";
  import { formatKwh, formatUah } from "@shared/utils/format";

  const dashboard = ref<AdminDashboardOut | null>(null);
  const dashboardError = ref<string | null>(null);
  const activeTab = ref("households");
  const isLoadingDashboard = ref(true);
  const locale = navigator.language;

  async function loadDashboard(): Promise<void> {
    isLoadingDashboard.value = true;
    dashboardError.value = null;

    try {
      dashboard.value = await getAdminDashboard();
    } catch (error) {
      dashboardError.value =
        error instanceof Error ? "errors.requestFailed" : "errors.requestFailed";
    } finally {
      isLoadingDashboard.value = false;
    }
  }

  onMounted(() => {
    void loadDashboard();
  });

  function ownerLabel(household: AdminDashboardOut["households"][number]): string {
    return household.owner ? `${household.owner.first_name} ${household.owner.last_name}` : "—";
  }

  function formatUsage(value: string | null | undefined): string {
    return formatKwh(value, locale, "kWh");
  }

  function formatCharge(value: string | null | undefined): string {
    return formatUah(value, locale);
  }
</script>

<style scoped lang="scss">
  .admin-header {
    margin-bottom: var(--s-app-space-6);

    &__title {
      color: var(--s-content-color);
      font-size: 1.6rem;
      font-weight: 700;
      margin: 0;
    }
  }

  .admin-body {
    max-width: none;
  }

  .admin-tabs {
    border-bottom: 1px solid var(--s-content-border-color);
    margin-bottom: var(--s-app-space-6);

    &__list {
      background: transparent;
      overflow-x: auto;
      scrollbar-width: thin;
    }

    :deep(.p-tablist) {
      background: transparent;
      border: 0;
    }

    :deep(.p-tablist-tab-list) {
      min-width: max-content;
    }

    :deep(.p-tab) {
      background: transparent;
      border: 0;
      border-bottom: 2px solid transparent;
      border-radius: 0;
      color: color-mix(in srgb, var(--s-content-color), transparent 38%);
      font-size: 0.875rem;
      font-weight: 600;
      min-height: 3rem;
      padding: 0 var(--s-app-space-4);
      transition:
        color 150ms ease,
        border-color 150ms ease,
        background-color 150ms ease;
    }

    :deep(.p-tab:hover) {
      background: color-mix(in srgb, var(--s-content-color), transparent 94%);
      color: var(--s-content-color);
    }

    :deep(.p-tab[aria-selected="true"]) {
      border-bottom-color: var(--s-primary-color);
      color: var(--s-primary-color);
    }

    :deep(.p-tab:focus-visible) {
      outline: 2px solid var(--s-primary-color);
      outline-offset: -2px;
    }
  }

  .admin-content-tabs {
    :deep(.p-tablist),
    :deep(.p-tablist-tab-list) {
      display: none;
    }

    :deep(.p-tabpanels) {
      background: transparent;
      padding: 0;
    }
  }

  .admin-error {
    align-items: center;
    background: color-mix(in srgb, var(--s-red-500), transparent 92%);
    border: 1px solid color-mix(in srgb, var(--s-red-500), transparent 65%);
    border-radius: var(--s-app-radius-md);
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-app-space-3);
    justify-content: space-between;
    padding: var(--s-app-space-3) var(--s-app-space-4);

    &__message {
      color: var(--s-content-color);
      margin: 0;
    }

    &__retry {
      background: var(--s-primary-color);
      border: 0;
      border-radius: var(--s-app-radius-sm);
      color: white;
      cursor: pointer;
      font: inherit;
      font-weight: 600;
      padding: 0.5rem 0.75rem;
    }
  }

  .admin-section {
    @include layout.stack(var(--s-app-space-3));
    max-width: 40rem;

    &--wide {
      max-width: none;
    }

    &__heading {
      align-items: center;
      display: flex;
      justify-content: space-between;
      min-width: 0;
    }

    &__title {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      margin: 0;
      text-transform: uppercase;
    }

    &__period {
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      font-size: 0.8rem;
      margin: var(--s-app-space-1) 0 0;
    }

    &__spinner {
      height: 1.25rem;
      width: 1.25rem;
    }
  }

  .admin-card {
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    overflow: hidden;

    &--padded {
      padding: var(--s-app-space-4);
    }

    &--table {
      overflow-x: auto;
    }
  }

  .admin-table {
    border-collapse: collapse;
    min-width: 42rem;
    width: 100%;

    th,
    td {
      border-bottom: 1px solid var(--s-content-border-color);
      padding: var(--s-app-space-3) var(--s-app-space-4);
      text-align: left;
      white-space: nowrap;
    }

    th {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
    }

    tbody th,
    td {
      color: var(--s-content-color);
      font-size: 0.9rem;
      font-weight: 500;
    }

    tr:last-child th,
    tr:last-child td {
      border-bottom: 0;
    }
  }

  .admin-status {
    border: 1px solid color-mix(in srgb, var(--s-content-color), transparent 70%);
    border-radius: var(--s-app-radius-sm);
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.25rem 0.5rem;

    &--submitted {
      border-color: var(--s-green-500);
      color: var(--s-green-800);
    }

    &--missing {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    }
  }
</style>

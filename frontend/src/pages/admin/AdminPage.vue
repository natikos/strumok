<template>
  <div class="admin-page">
    <header class="admin-header">
      <h1 class="admin-header__title">{{ $t("admin.title") }}</h1>
    </header>

    <div class="admin-body">
      <section class="admin-section">
        <h2 class="admin-section__title">{{ $t("admin.householdAssignment") }}</h2>

        <div class="admin-card admin-card--padded">
          <AdminHouseholdAssignment />
        </div>
      </section>

      <section class="admin-section">
        <h2 class="admin-section__title">{{ $t("admin.electricityRates") }}</h2>

        <div class="admin-card admin-card--padded">
          <ElectricityRatesSettings />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
  import AdminHouseholdAssignment from "@features/admin/AdminHouseholdAssignment.vue";
  import ElectricityRatesSettings from "@features/admin/ElectricityRatesSettings.vue";
</script>

<style scoped lang="scss">
  .admin-page {
    padding: var(--s-app-space-5);

    @media (min-width: 60rem) {
      padding: var(--s-app-space-8);
    }
  }

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
    @include layout.stack(var(--s-app-space-8));
    max-width: 40rem;
  }

  .admin-section {
    @include layout.stack(var(--s-app-space-3));

    &__title {
      color: color-mix(in srgb, var(--s-content-color), transparent 35%);
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      margin: 0;
      text-transform: uppercase;
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
  }
</style>

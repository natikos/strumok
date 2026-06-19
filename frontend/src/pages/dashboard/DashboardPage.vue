<template>
  <div class="dashboard-home">
    <section class="dashboard-welcome" aria-live="polite">
      <h1 class="dashboard-welcome__title">
        {{ me ? $t("dashboard.welcomeTitle", { name: me.first_name }) : $t("dashboard.loadingTitle") }}
      </h1>
      <p v-if="me" class="dashboard-welcome__sub">
        {{ subgreeting }}
      </p>
    </section>

    <div class="dashboard-cards">
      <MeterReadingsCard :user-name="me?.first_name ?? ''" />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import MeterReadingsCard from "@features/meter-readings/MeterReadingsCard.vue";
  import { useLocale } from "@features/i18n/composables/useLocale";
  import { getMe } from "@shared/api/auth";
  import type { components } from "@shared/api/generated/openapi";

  type UserOut = components["schemas"]["UserOut"];

  const me = ref<UserOut | null>(null);
  const { t } = useI18n();
  const { currentLocale } = useLocale();

  const intlLocale = computed(() => (currentLocale.value === "ua" ? "uk-UA" : "en-US"));

  const DEADLINE_DAY = 10;

  const currentMonthLong = computed(() => {
    const date = new Date();
    date.setDate(1);
    const label = new Intl.DateTimeFormat(intlLocale.value, { month: "long" }).format(date);
    return label.charAt(0).toUpperCase() + label.slice(1);
  });

  // We rely on MeterReadingsCard to know submission state, so use a simple
  // date-based heuristic for the subgreeting: after deadline day = overdue.
  // The MeterReadingsCard handles the real submitted state internally.
  const subgreeting = computed(() => {
    const today = new Date();
    if (today.getDate() > DEADLINE_DAY) {
      return t("dashboard.subgreetingOverdue", { month: currentMonthLong.value });
    }
    return t("dashboard.subgreeting", { month: currentMonthLong.value });
  });

  onMounted(async () => {
    me.value = await getMe();
  });
</script>

<style scoped lang="scss">
  .dashboard-home {
    padding: var(--s-app-space-4);

    @media (min-width: 60rem) {
      padding: var(--s-app-space-6);
    }
  }

  .dashboard-welcome {
    margin-bottom: var(--s-app-space-4);

    &__title {
      color: var(--s-content-color);
      font-size: 1.7rem;
      margin: 0 0 var(--s-app-space-1);
    }

    &__sub {
      color: color-mix(in srgb, var(--s-content-color), transparent 30%);
      font-size: 1rem;
      margin: 0;
      line-height: 1.4;
    }
  }

  .dashboard-cards {
    @include layout.stack(var(--s-app-space-4));
  }
</style>

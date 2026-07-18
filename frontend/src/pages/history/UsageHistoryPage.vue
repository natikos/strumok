<template>
  <div class="usage-history">
    <header class="usage-history__header">
      <h1 class="usage-history__title">{{ $t("usageHistory.title") }}</h1>
    </header>

    <section
      v-if="!isLoading && summary"
      class="usage-history__summary"
      :aria-label="$t('usageHistory.summaryAria')"
    >
      <div class="usage-history__summary-cell">
        <span class="usage-history__summary-label">
          {{ $t("usageHistory.summaryMonths", { count: summary.monthCount }) }}
        </span>
        <span class="usage-history__summary-value">
          {{ formatKwh(summary.totalUsage) }}
        </span>
      </div>
      <div class="usage-history__summary-cell">
        <span class="usage-history__summary-label">
          {{ $t("usageHistory.summaryCharged") }}
        </span>
        <span class="usage-history__summary-value">
          {{ formatUah(summary.totalCharged) }}
        </span>
      </div>
    </section>

    <div v-if="!isLoading && groups.length === 0" class="usage-history__empty">
      <i class="pi pi-inbox usage-history__empty-icon" aria-hidden="true"></i>
      <h2 class="usage-history__empty-title">{{ $t("usageHistory.emptyTitle") }}</h2>
      <p class="usage-history__empty-description">
        {{ $t("usageHistory.emptyDescription") }}
      </p>
      <Button
        as="router-link"
        :to="ROUTES.root"
        :label="$t('usageHistory.emptyCta')"
        icon="pi pi-arrow-right"
        icon-pos="right"
      />
    </div>

    <template v-else>
      <section v-for="group in groups" :key="group.year" class="usage-history__group">
        <div class="usage-history__group-head">
          <h2 class="usage-history__group-year">{{ group.year }}</h2>
          <span class="usage-history__group-summary">
            <span class="usage-history__group-summary-value">
              {{ formatKwh(group.totalUsage) }}
            </span>
            <span class="usage-history__group-summary-sep" aria-hidden="true">·</span>
            <span class="usage-history__group-summary-value">
              {{ formatUah(group.totalCharged) }}
            </span>
          </span>
        </div>
        <ol class="usage-history__list">
          <li v-for="entry in group.entries" :key="entry.period" class="usage-history__item">
            <div class="usage-history__item-head">
              <span class="usage-history__month">{{ entry.monthLabel }}</span>
            </div>

            <div class="usage-history__metrics">
              <div
                class="usage-history__metric"
                :class="{ 'usage-history__metric--negative': entry.dayUsage < 0 }"
              >
                <span class="usage-history__metric-label">
                  <i class="pi pi-sun" aria-hidden="true"></i>
                  {{ $t("usageHistory.day") }}
                </span>
                <span class="usage-history__metric-value">
                  {{ formatKwh(entry.dayUsage) }}
                </span>
              </div>
              <div
                class="usage-history__metric"
                :class="{ 'usage-history__metric--negative': entry.nightUsage < 0 }"
              >
                <span class="usage-history__metric-label">
                  <i class="pi pi-moon" aria-hidden="true"></i>
                  {{ $t("usageHistory.night") }}
                </span>
                <span class="usage-history__metric-value">
                  {{ formatKwh(entry.nightUsage) }}
                </span>
              </div>
              <div class="usage-history__metric usage-history__metric--total">
                <span class="usage-history__metric-label">
                  {{ $t("usageHistory.total") }}
                </span>
                <span class="usage-history__metric-value">
                  {{ formatKwh(entry.totalUsage) }}
                </span>
              </div>
            </div>

            <div
              class="usage-history__charge"
              :class="{ 'usage-history__charge--credit': entry.amountCharged < 0 }"
            >
              <span class="usage-history__charge-label">
                {{ $t("usageHistory.charged") }}
              </span>
              <span class="usage-history__charge-value">
                {{ formatUah(entry.amountCharged) }}
                <span v-if="entry.amountCharged < 0" class="usage-history__charge-tag">
                  {{ $t("usageHistory.credit") }}
                </span>
              </span>
            </div>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import { useCurrentHousehold } from "@features/households/useCurrentHousehold";
  import { useLocale } from "@features/i18n/composables/useLocale";
  import { listMyMeterReadings, type MeterReadingOut } from "@shared/api/meter-readings";
  import { ROUTES } from "@shared/routing/routes";

  interface HistoryEntry {
    period: string;
    year: string;
    monthLabel: string;
    dayUsage: number;
    nightUsage: number;
    totalUsage: number;
    amountCharged: number;
  }

  interface YearGroup {
    year: string;
    entries: HistoryEntry[];
    totalUsage: number;
    totalCharged: number;
  }

  const readings = ref<MeterReadingOut[]>([]);
  const isLoading = ref(true);

  const { t } = useI18n();
  const { intlLocale } = useLocale();
  const { currentId } = useCurrentHousehold();

  function periodToDate(period: string): Date {
    const [yearStr, monthStr] = period.split("-");
    return new Date(Number(yearStr), Number(monthStr) - 1, 1);
  }

  const sortedEntries = computed<HistoryEntry[]>(() => {
    const entries = readings.value.map((reading) => {
      const date = periodToDate(reading.period);
      const dayUsage = Number(reading.day_usage_kwh);
      const nightUsage = Number(reading.night_usage_kwh);
      return {
        period: reading.period,
        year: String(date.getFullYear()),
        monthLabel: new Intl.DateTimeFormat(intlLocale.value, { month: "long" }).format(date),
        dayUsage,
        nightUsage,
        totalUsage: dayUsage + nightUsage,
        amountCharged: Number(reading.amount_charged_uah),
      };
    });
    return entries.sort((a, b) => (a.period < b.period ? 1 : -1));
  });

  const groups = computed<YearGroup[]>(() => {
    const map = new Map<string, HistoryEntry[]>();
    for (const entry of sortedEntries.value) {
      const list = map.get(entry.year);
      if (list) list.push(entry);
      else map.set(entry.year, [entry]);
    }
    return Array.from(map, ([year, entries]) => ({
      year,
      entries,
      totalUsage: entries.reduce((sum, e) => sum + e.totalUsage, 0),
      totalCharged: entries.reduce((sum, e) => sum + e.amountCharged, 0),
    }));
  });

  const summary = computed(() => {
    if (sortedEntries.value.length === 0) return null;
    return sortedEntries.value.reduce(
      (acc, entry) => ({
        monthCount: acc.monthCount + 1,
        totalUsage: acc.totalUsage + entry.totalUsage,
        totalCharged: acc.totalCharged + entry.amountCharged,
      }),
      { monthCount: 0, totalUsage: 0, totalCharged: 0 }
    );
  });

  function formatKwh(value: number): string {
    return `${value.toLocaleString(intlLocale.value, { maximumFractionDigits: 2 })} ${t("units.kwh")}`;
  }

  function formatUah(value: number): string {
    return value.toLocaleString(intlLocale.value, {
      style: "currency",
      currency: "UAH",
      maximumFractionDigits: 2,
    });
  }

  async function loadReadings(): Promise<void> {
    isLoading.value = true;
    try {
      readings.value = await listMyMeterReadings(currentId.value);
    } finally {
      isLoading.value = false;
    }
  }

  onMounted(loadReadings);

  watch(currentId, () => {
    void loadReadings();
  });
</script>

<style scoped lang="scss">
  .usage-history__header {
    margin-bottom: var(--s-app-space-5);
  }

  .usage-history__title {
    color: var(--s-content-color);
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0;
  }

  .usage-history__summary {
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    display: grid;
    gap: var(--s-app-space-3);
    grid-template-columns: 1fr 1fr;
    margin-bottom: var(--s-app-space-5);
    padding: var(--s-app-space-4);
  }

  .usage-history__summary-cell {
    @include layout.stack(0.25rem);
    min-width: 0;
  }

  .usage-history__summary-label {
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    font-size: 0.75rem;
    text-transform: uppercase;
  }

  .usage-history__summary-value {
    color: var(--s-content-color);
    font-size: 1.25rem;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
  }

  .usage-history__empty {
    @include layout.stack(var(--s-app-space-3));
    align-items: center;
    padding: var(--s-app-space-8) var(--s-app-space-4);
    text-align: center;
  }

  .usage-history__empty-icon {
    color: color-mix(in srgb, var(--s-content-color), transparent 65%);
    font-size: 2.5rem;
  }

  .usage-history__empty-title {
    color: var(--s-content-color);
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0;
  }

  .usage-history__empty-description {
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    font-size: 0.9rem;
    margin: 0;
    max-width: 24rem;
  }

  .usage-history__group {
    @include layout.stack(var(--s-app-space-2));

    & + & {
      margin-top: var(--s-app-space-5);
    }
  }

  .usage-history__group-head {
    align-items: baseline;
    column-gap: var(--s-app-space-3);
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    margin: 0 0 var(--s-app-space-1);
  }

  .usage-history__group-year {
    color: color-mix(in srgb, var(--s-content-color), transparent 35%);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    margin: 0;
    text-transform: uppercase;
  }

  .usage-history__group-summary {
    align-items: baseline;
    color: color-mix(in srgb, var(--s-content-color), transparent 25%);
    column-gap: var(--s-app-space-2);
    display: inline-flex;
    flex-wrap: wrap;
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }

  .usage-history__group-summary-sep {
    color: color-mix(in srgb, var(--s-content-color), transparent 60%);
  }

  .usage-history__list {
    @include layout.stack(var(--s-app-space-2));
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .usage-history__item {
    background: var(--s-content-background);
    border: 1px solid var(--s-content-border-color);
    border-radius: var(--s-app-radius-md);
    display: grid;
    gap: var(--s-app-space-3);
    grid-template-columns: 1fr;
    padding: var(--s-app-space-4);

    @media (min-width: 45rem) {
      align-items: center;
      grid-template-columns: 7rem 1fr 9rem;
      gap: var(--s-app-space-5);
    }
  }

  .usage-history__item-head {
    align-items: baseline;
    column-gap: var(--s-app-space-2);
    display: flex;
  }

  .usage-history__month {
    color: var(--s-content-color);
    font-size: 1.05rem;
    font-weight: 600;
    text-transform: capitalize;
  }

  .usage-history__metrics {
    display: grid;
    gap: var(--s-app-space-2);
    grid-template-columns: repeat(3, 1fr);
  }

  .usage-history__metric {
    @include layout.stack(0.1rem);
    min-width: 0;
  }

  .usage-history__metric--total .usage-history__metric-value {
    font-weight: 700;
  }

  .usage-history__metric--negative .usage-history__metric-value {
    color: var(--s-primary-900);
  }

  .usage-history__metric-label {
    align-items: center;
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    column-gap: var(--s-app-space-1);
    display: inline-flex;
    font-size: 0.75rem;
    text-transform: uppercase;

    i {
      font-size: 0.85rem;
    }
  }

  .usage-history__metric-label i.pi-sun {
    color: var(--s-amber-500, #f59e0b);
  }

  .usage-history__metric-label i.pi-moon {
    color: var(--s-primary-900);
  }

  .usage-history__metric-value {
    color: var(--s-content-color);
    font-size: 0.95rem;
    font-variant-numeric: tabular-nums;
  }

  .usage-history__charge {
    @include layout.stack(0.1rem);
    align-items: flex-start;

    @media (min-width: 45rem) {
      align-items: flex-end;
      text-align: right;
    }
  }

  .usage-history__charge-label {
    color: color-mix(in srgb, var(--s-content-color), transparent 40%);
    font-size: 0.75rem;
    text-transform: uppercase;
  }

  .usage-history__charge-value {
    align-items: baseline;
    color: var(--s-content-color);
    column-gap: var(--s-app-space-1);
    display: inline-flex;
    flex-wrap: wrap;
    font-size: 1.05rem;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
  }

  .usage-history__charge--credit .usage-history__charge-value {
    color: var(--s-primary-900);
  }

  .usage-history__charge-tag {
    background: color-mix(in srgb, var(--s-primary-900), transparent 85%);
    border-radius: var(--s-app-radius-sm);
    color: var(--s-primary-900);
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.1rem 0.4rem;
    text-transform: uppercase;
  }
</style>

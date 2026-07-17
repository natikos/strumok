<template>
  <div class="deadline-badge" :class="`deadline-badge--${status}`">
    <i :class="icon" aria-hidden="true"></i>
    {{ t(`statuses.meterReading.${toCamelCase(status)}`) }}
  </div>
</template>

<script setup lang="ts">
  import { toCamelCase } from "@utils/string";
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import { type DeadlineStatus, getDeadlineStatus } from "@/features/meter-readings/deadline";
  import type { MeterReadingOut } from "@shared/api/meter-readings";

  interface Props {
    reading: MeterReadingOut | null | undefined;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const status = computed(() => getDeadlineStatus(props.reading?.submitted_at));

  const icon = computed(() => {
    const ICONS: Record<DeadlineStatus, string> = {
      submitted: "pi pi-check-circle",
      "submitted-late": "pi pi-exclamation-triangle",
      overdue: "pi pi-times-circle",
      due: "pi pi-clock",
    } as const;
    return ICONS[status.value];
  });
</script>

<style scoped lang="scss">
  .deadline-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--s-app-space-1);
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.3em 0.85em;
    border-radius: 2rem;
    white-space: nowrap;

    &--due {
      background: color-mix(in srgb, var(--s-primary-color), transparent 88%);
      color: var(--s-primary-color);
    }

    &--overdue {
      background: color-mix(in srgb, var(--s-red-500), transparent 88%);
      color: var(--s-red-500);
    }

    &--submitted {
      background: color-mix(in srgb, var(--s-green-500), transparent 88%);
      color: var(--s-green-800);
    }

    &--submitted-late {
      background: color-mix(in srgb, var(--s-amber-500), transparent 88%);
      color: var(--s-amber-800);
    }
  }
</style>

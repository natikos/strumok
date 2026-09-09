<template>
  <div
    class="window-strip"
    :class="{ 'window-strip--overdue': isOverdue }"
    role="img"
    :aria-label="ariaLabel"
  >
    <div class="window-strip__track">
      <span
        v-for="segment in segments"
        :key="segment.day"
        class="window-strip__segment"
        :class="`window-strip__segment--${segment.state}`"
      ></span>
    </div>
    <div class="window-strip__captions">
      <span
        v-for="segment in segments"
        :key="segment.day"
        class="window-strip__caption"
        :class="{ 'window-strip__caption--today': segment.isToday }"
      >
        {{ segment.day }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import { DEADLINE_DAY } from "@shared/utils/deadline";

  interface Props {
    isOverdue?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), { isOverdue: false });

  const { t } = useI18n();

  type SegmentState = "elapsed" | "today" | "future";

  const segments = computed(() => {
    const today = new Date().getDate();

    return Array.from({ length: DEADLINE_DAY }, (_, index) => {
      const day = index + 1;

      let state: SegmentState = "future";
      if (props.isOverdue || day < today) {
        state = "elapsed";
      } else if (day === today) {
        state = "today";
      }

      return { day, isToday: day === today && !props.isOverdue, state };
    });
  });

  const ariaLabel = computed(() => {
    const elapsed = segments.value.filter((segment) => segment.state === "elapsed").length;
    return t("deadlineStatus.stripAriaLabel", {
      day: DEADLINE_DAY,
      elapsed,
      total: DEADLINE_DAY,
    });
  });
</script>

<style scoped lang="scss">
  .window-strip {
    @include layout.stack(var(--s-app-space-1));

    &__track,
    &__captions {
      display: flex;
      gap: var(--s-app-space-1);
    }

    &__segment {
      flex: 1;
      height: 6px;
      border-radius: 3px;
      background: var(--s-surface-200);
      min-width: 0;

      &--elapsed {
        background: var(--s-primary-color);
      }

      &--today {
        background: color-mix(in srgb, var(--s-primary-color), transparent 40%);
      }
    }

    &__caption {
      flex: 1;
      text-align: center;
      font-size: 0.7rem;
      color: color-mix(in srgb, var(--s-content-color), transparent 40%);
      min-width: 0;

      &--today {
        font-weight: 700;
        color: var(--s-content-color);
      }
    }

    // Overdue: the whole window has closed, so every segment reads as spent.
    &--overdue &__segment--elapsed {
      background: var(--s-red-500);
    }
  }
</style>

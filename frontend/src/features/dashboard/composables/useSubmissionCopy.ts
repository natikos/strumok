import { computed, type ComputedRef } from "vue";
import { useI18n } from "vue-i18n";

import { DEADLINE_DAY, type DeadlineStatus } from "@shared/utils/deadline";

export interface SubmissionCopyInput {
  status: DeadlineStatus;
  daysLeft: number;
  deadlineMonthIndex: number;
  isFirstPeriod: boolean;
  submittedAt: string | null | undefined;
  intlLocale: string;
}

/**
 * Headline/subline/submit-label copy for every deadline status, kept in one
 * place so a new status can't update one switch and miss another.
 */
export function useSubmissionCopy(props: ComputedRef<SubmissionCopyInput>) {
  const { locale, t } = useI18n();

  const deadlineMonth = computed(() =>
    t(`months.${locale.value === "ua" ? "genitive" : "long"}.${props.value.deadlineMonthIndex}`)
  );

  const formattedSubmittedAt = computed(() => {
    const submittedAt = props.value.submittedAt;
    if (!submittedAt) {
      return "";
    }
    return new Date(submittedAt).toLocaleString(props.value.intlLocale, {
      day: "numeric",
      month: "long",
      hour: "2-digit",
      minute: "2-digit",
    });
  });

  const headline = computed(() => {
    const { status, isFirstPeriod, daysLeft } = props.value;

    if (isFirstPeriod && status === "due") {
      return t("deadlineStatus.firstPeriodHeadline");
    }

    switch (status) {
      case "due":
        return t("deadlineStatus.daysLeft", { count: daysLeft }, daysLeft);
      case "submitted":
      case "submitted-late":
        return t("deadlineStatus.submittedHeadline");
      case "overdue":
        return t("deadlineStatus.overdueHeadline");
      default:
        return t("deadlineStatus.daysLeft", { count: daysLeft }, daysLeft);
    }
  });

  const subline = computed(() => {
    const { status, isFirstPeriod } = props.value;

    if (isFirstPeriod && status === "due") {
      return t("deadlineStatus.firstPeriodExplainer");
    }

    switch (status) {
      case "due":
        return t("deadlineStatus.windowClosesAt", {
          day: DEADLINE_DAY,
          month: deadlineMonth.value,
        });
      case "submitted":
        return t("deadlineStatus.submittedDetail", {
          date: formattedSubmittedAt.value,
          day: DEADLINE_DAY,
          month: deadlineMonth.value,
        });
      case "submitted-late":
        return t("deadlineStatus.submittedLateDetail");
      case "overdue":
        return t("deadlineStatus.windowClosedAt", {
          day: DEADLINE_DAY,
          month: deadlineMonth.value,
        });
      default:
        return t("deadlineStatus.windowClosesAt", {
          day: DEADLINE_DAY,
          month: deadlineMonth.value,
        });
    }
  });

  const submitLabel = computed(() => {
    const { status, isFirstPeriod } = props.value;

    if (status === "overdue") {
      return t("meterReadings.submitLate");
    }
    return isFirstPeriod ? t("meterReadings.submitFirst") : t("meterReadings.submit");
  });

  return { headline, subline, submitLabel };
}

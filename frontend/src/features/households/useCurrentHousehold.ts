import { computed, ref } from "vue";

import type { components } from "@shared/api/generated/openapi";

export type HouseholdSummary = components["schemas"]["HouseholdSummary"];

const STORAGE_KEY = "strumok:current-household-id";
// Remembered so a household that disappears between sessions (deactivated by
// the head) can still be named in the "switched to" notice.
const NAME_STORAGE_KEY = "strumok:current-household-name";

export interface HouseholdSwitch {
  removedName: string | null;
  switchedTo: HouseholdSummary | null;
}

const households = ref<HouseholdSummary[]>([]);
const currentId = ref<number | null>(readStoredId());

function readStoredId(): number | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  const parsed = raw ? Number(raw) : NaN;
  return Number.isFinite(parsed) ? parsed : null;
}

function writeStored(household: HouseholdSummary | null): void {
  if (household === null) {
    window.localStorage.removeItem(STORAGE_KEY);
    window.localStorage.removeItem(NAME_STORAGE_KEY);
  } else {
    window.localStorage.setItem(STORAGE_KEY, String(household.id));
    window.localStorage.setItem(NAME_STORAGE_KEY, household.name);
  }
}

export function useCurrentHousehold() {
  const current = computed<HouseholdSummary | null>(
    () => households.value.find((h) => h.id === currentId.value) ?? null
  );

  /** Returns what changed when the remembered household is no longer listed. */
  function setHouseholds(next: HouseholdSummary[]): HouseholdSwitch | null {
    const previousId = currentId.value;
    const previousName =
      households.value.find((h) => h.id === previousId)?.name ??
      window.localStorage.getItem(NAME_STORAGE_KEY);
    households.value = next;

    if (next.some((h) => h.id === previousId)) {
      return null;
    }

    const fallback = next[0] ?? null;
    currentId.value = fallback?.id ?? null;
    writeStored(fallback);

    return previousId === null ? null : { removedName: previousName, switchedTo: fallback };
  }

  function setCurrent(id: number): void {
    currentId.value = id;
    writeStored(households.value.find((h) => h.id === id) ?? null);
  }

  return {
    households: computed(() => households.value),
    current,
    currentId: computed(() => currentId.value),
    setHouseholds,
    setCurrent,
  };
}

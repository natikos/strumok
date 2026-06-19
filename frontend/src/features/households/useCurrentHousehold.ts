import { computed, ref } from "vue";

import type { components } from "@shared/api/generated/openapi";

export type HouseholdSummary = components["schemas"]["HouseholdSummary"];

const STORAGE_KEY = "strumok:current-household-id";

const households = ref<HouseholdSummary[]>([]);
const currentId = ref<number | null>(readStoredId());

function readStoredId(): number | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  const parsed = raw ? Number(raw) : NaN;
  return Number.isFinite(parsed) ? parsed : null;
}

function writeStoredId(id: number | null): void {
  if (id === null) {
    window.localStorage.removeItem(STORAGE_KEY);
  } else {
    window.localStorage.setItem(STORAGE_KEY, String(id));
  }
}

export function useCurrentHousehold() {
  const current = computed<HouseholdSummary | null>(
    () => households.value.find((h) => h.id === currentId.value) ?? null,
  );

  function setHouseholds(next: HouseholdSummary[]): void {
    households.value = next;

    const stillExists = next.some((h) => h.id === currentId.value);

    if (!stillExists) {
      const fallback = next[0]?.id ?? null;
      currentId.value = fallback;
      writeStoredId(fallback);
    }
  }

  function setCurrent(id: number): void {
    currentId.value = id;
    writeStoredId(id);
  }

  return {
    households: computed(() => households.value),
    current,
    currentId: computed(() => currentId.value),
    setHouseholds,
    setCurrent,
  };
}

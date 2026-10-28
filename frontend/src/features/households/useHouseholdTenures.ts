import { computed, ref } from "vue";

import { type HouseholdStatementsOut, listMyStatements } from "@shared/api/billing";
import { toDecimal } from "@shared/utils/format";

// Shared across the dashboard notice, the balance strip and history so one page
// view costs one request. A failure leaves the list empty: these are extras on
// top of the current household's own data, never a reason to blank a screen.
const tenures = ref<HouseholdStatementsOut[]>([]);
let inflight: Promise<void> | null = null;

export function useHouseholdTenures() {
  async function load(): Promise<void> {
    inflight ??= listMyStatements()
      .then((rows) => {
        tenures.value = rows;
      })
      .catch(() => {
        tenures.value = [];
      })
      .finally(() => {
        inflight = null;
      });

    return inflight;
  }

  const past = computed(() => tenures.value.filter((t) => !t.is_current_owner));
  const pastBalance = computed(() =>
    past.value.reduce((sum, t) => sum + toDecimal(t.balance.balance_uah), 0)
  );

  function forHousehold(id: number | null): HouseholdStatementsOut | null {
    return tenures.value.find((t) => t.household_id === id) ?? null;
  }

  return { tenures, past, pastBalance, forHousehold, load };
}

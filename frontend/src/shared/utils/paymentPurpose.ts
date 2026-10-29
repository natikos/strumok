// Must stay in sync with household_reference() in backend/app/api/bank/matching.
const REFERENCE_PREFIX = "STR";

export function householdReference(householdId: number): string {
  return `${REFERENCE_PREFIX}-${householdId}`;
}

export function paymentPurpose(label: string, householdIds: number[]): string {
  const refs = [...householdIds].sort((a, b) => a - b).map(householdReference);

  return refs.length ? `${label} ${refs.join(", ")}` : label;
}

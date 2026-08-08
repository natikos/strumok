export function formatMeterValue(
  value: number | string | null | undefined,
  locale: string
): string {
  if (value == null) {
    return "—";
  }
  const numeric = typeof value === "string" ? Number(value) : value;
  return numeric.toLocaleString(locale, { maximumFractionDigits: 2 });
}

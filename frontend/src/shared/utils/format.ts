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

/**
 * Coerce an API Decimal field (kWh, hryvnia) to a number.
 *
 * The backend emits Decimal as a JSON string, so summing two of these raw
 * ("10.00" + "5.00" → "10.005.00") is a real and silent bug. Every derived
 * value goes through here instead of an inline `Number(...)` at the call site.
 */
export function toDecimal(value: number | string | null | undefined): number {
  if (value == null) {
    return 0;
  }
  const numeric = typeof value === "string" ? Number(value) : value;
  return Number.isFinite(numeric) ? numeric : 0;
}

/** A kWh figure with its unit — no bare energy number is ever shown in the UI. */
export function formatKwh(
  value: number | string | null | undefined,
  locale: string,
  unit: string
): string {
  return `${formatMeterValue(value, locale)} ${unit}`;
}

/** A hryvnia amount, always to two decimal places. */
export function formatUah(value: number | string | null | undefined, locale: string): string {
  if (value == null) {
    return "—";
  }
  const numeric = typeof value === "string" ? Number(value) : value;
  return numeric.toLocaleString(locale, {
    style: "currency",
    currency: "UAH",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

import type { AdjustmentOut, StatementLineOut } from "@shared/api/billing";

/** "123.45" -> 12345. Money is summed as integer kopecks so lines add up exactly. */
export function toKopecks(value: string | number | null | undefined): number {
  if (value == null) {
    return 0;
  }

  return Math.round(Number(value) * 100);
}

export type BillRowKind =
  | "correction"
  | "lateFee"
  | "lateFeeCredit"
  | "sharedLosses"
  | "tariff";

export interface BillRow {
  kind: BillRowKind;
  /** Signed kopecks: credits and refunds are negative. */
  kopecks: number;
  reason?: string;
}

export interface Bill {
  period: string;
  isEstimated: boolean;
  isProvisional: boolean;
  usageKwh: number;
  rows: BillRow[];
  /** Always the exact sum of `rows`. */
  totalKopecks: number;
}

/**
 * Turns a statement line (and the corrections that apply to its period) into
 * the rows a resident sees. The total is the sum of the rows by construction,
 * and the statement's own total must agree with the rows without corrections.
 */
export function buildBill(line: StatementLineOut, adjustments: AdjustmentOut[]): Bill {
  const rows: BillRow[] = [{ kind: "tariff", kopecks: toKopecks(line.tariff_uah) }];

  const loss = toKopecks(line.loss_share_uah);
  if (loss !== 0) {
    rows.push({ kind: "sharedLosses", kopecks: loss });
  }

  const penalty = toKopecks(line.penalty_uah);
  if (penalty !== 0) {
    rows.push({ kind: "lateFee", kopecks: penalty });
  }

  const credit = toKopecks(line.penalty_credit_uah);
  if (credit !== 0) {
    rows.push({ kind: "lateFeeCredit", kopecks: -credit });
  }

  for (const adjustment of adjustments) {
    if (adjustment.applies_to_period === line.period) {
      rows.push({
        kind: "correction",
        kopecks: toKopecks(adjustment.amount_uah),
        reason: adjustment.reason,
      });
    }
  }

  return {
    period: line.period,
    isEstimated: line.is_estimated,
    isProvisional: line.status === "provisional",
    usageKwh: Number(line.day_usage_kwh) + Number(line.night_usage_kwh),
    rows,
    totalKopecks: rows.reduce((sum, row) => sum + row.kopecks, 0),
  };
}

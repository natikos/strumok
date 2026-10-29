import { describe, expect, it } from "vitest";

import type { AdjustmentOut, StatementLineOut } from "@shared/api/billing";

import { buildBill, toKopecks } from "./bill";

function line(overrides: Partial<StatementLineOut> = {}): StatementLineOut {
  return {
    day_usage_kwh: "100.00",
    is_estimated: false,
    loss_share_uah: "12.34",
    night_usage_kwh: "40.00",
    penalty_credit_uah: "0.00",
    penalty_uah: "0.00",
    period: "2026-09",
    status: "closed",
    tariff_uah: "500.10",
    total_uah: "512.44",
    ...overrides,
  };
}

const adjustment = (overrides: Partial<AdjustmentOut> = {}): AdjustmentOut => ({
  amount_uah: "-12.40",
  applies_to_period: "2026-09",
  id: 1,
  posted_in_period: "2026-10",
  reason: "bill corrected",
  reason_code: "billCorrection",
  ...overrides,
});

describe("buildBill", () => {
  it("rows add up exactly to the statement total (Decimal strings, no float drift)", () => {
    const bill = buildBill(line(), []);

    expect(bill.totalKopecks).toBe(toKopecks("512.44"));
    expect(bill.rows.map((r) => r.kind)).toEqual(["tariff", "sharedLosses"]);
  });

  it("labels the late fee and its credit as separate signed rows", () => {
    const estimated = buildBill(
      line({
        is_estimated: true,
        loss_share_uah: "0.00",
        penalty_uah: "30.00",
        total_uah: "530.10",
      }),
      []
    );
    const credited = buildBill(
      line({ loss_share_uah: "0.00", penalty_credit_uah: "7.50", total_uah: "492.60" }),
      []
    );

    expect(estimated.isEstimated).toBe(true);
    expect(estimated.totalKopecks).toBe(53010);
    expect(credited.rows.at(-1)).toEqual({ kind: "lateFeeCredit", kopecks: -750 });
    expect(credited.totalKopecks).toBe(49260);
  });

  it("includes only the corrections that apply to this period, each with its reason", () => {
    const bill = buildBill(line(), [
      adjustment(),
      adjustment({ amount_uah: "99.00", applies_to_period: "2026-08", id: 2 }),
    ]);

    const corrections = bill.rows.filter((r) => r.kind === "correction");
    expect(corrections).toEqual([{ kind: "correction", kopecks: -1240, reason: "bill corrected" }]);
    expect(bill.totalKopecks).toBe(toKopecks("512.44") - 1240);
  });

  it("marks the open period's figure as provisional", () => {
    expect(buildBill(line({ status: "provisional" }), []).isProvisional).toBe(true);
  });
});

import type { components } from "./generated/openapi.ts";

import { appApiClient, buildApiError } from "./client";

export type RestatementOut = components["schemas"]["RestatementOut"];
export type ElectricityRateOut = components["schemas"]["ElectricityRateOut"];
type ElectricityRateCreateIn = components["schemas"]["ElectricityRateCreateIn"];

export const EFFECTIVE_FROM_ALREADY_EXISTS_ERROR_CODE = "effectiveFromAlreadyExists";

export async function listElectricityRates(): Promise<ElectricityRateOut[]> {
  const { data } = await appApiClient.GET("/electricity-rates");

  return data ?? [];
}

export async function createElectricityRate(
  payload: ElectricityRateCreateIn
): Promise<ElectricityRateOut> {
  const { data, error, response } = await appApiClient.POST("/electricity-rates", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function updateElectricityRate(
  rateId: number,
  payload: { day_rate_uah?: string; night_rate_uah?: string; reason?: string }
): Promise<ElectricityRateOut> {
  const { data, error, response } = await appApiClient.PATCH("/electricity-rates/{rate_id}", {
    body: { ...payload, confirm: true },
    params: { path: { rate_id: rateId } },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function deleteElectricityRate(rateId: number, reason?: string): Promise<void> {
  const { error, response } = await appApiClient.DELETE("/electricity-rates/{rate_id}", {
    params: {
      path: { rate_id: rateId },
      query: { confirm: true, ...(reason ? { reason } : {}) },
    },
  });

  if (!response.ok) {
    throw buildApiError(response.status, error);
  }
}

export async function correctElectricityRate(
  rateId: number,
  rates: { day_rate_uah: string; night_rate_uah: string },
  options: { dryRun: boolean; reason: string }
): Promise<RestatementOut> {
  const { data, error, response } = await appApiClient.POST("/electricity-rates/{rate_id}/correct", {
    body: { ...rates, confirm: true, dry_run: options.dryRun, reason: options.reason || null },
    params: { path: { rate_id: rateId } },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

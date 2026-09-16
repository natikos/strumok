import type { components } from "./generated/openapi.ts";

import { appApiClient, buildApiError } from "./client";

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

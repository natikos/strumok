import type { components } from "./generated/openapi.ts";

import { appApiClient, buildApiError } from "./client";

type MeterReadingIn = components["schemas"]["MeterReadingIn"];
export type MeterReadingOut = components["schemas"]["MeterReadingOut"];

export async function listMyMeterReadings(
  householdId?: number | null,
): Promise<MeterReadingOut[]> {
  const { data, error, response } = await appApiClient.GET("/meter-readings", {
    params: {
      query: householdId == null ? {} : { household_id: householdId },
    },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function submitMyMeterReading(
  payload: MeterReadingIn,
  householdId?: number | null,
): Promise<MeterReadingOut> {
  const { data, error, response } = await appApiClient.POST("/meter-readings", {
    params: {
      query: householdId == null ? {} : { household_id: householdId },
    },
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

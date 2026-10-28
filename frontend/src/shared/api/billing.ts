import type { components } from "./generated/openapi.ts";

import { appApiClient, buildApiError } from "./client";

export type StatementLineOut = components["schemas"]["StatementLineOut"];
export type BalanceOut = components["schemas"]["BalanceOut"];
export type AdjustmentOut = components["schemas"]["AdjustmentOut"];
export type HouseholdStatementsOut = components["schemas"]["HouseholdStatementsOut"];
export type CurrentPeriodOut = components["schemas"]["CurrentPeriodOut"];

export async function getCurrentPeriod(): Promise<CurrentPeriodOut> {
  const { data } = await appApiClient.GET("/billing/current-period");

  if (!data) {
    throw new Error("Current period response was empty");
  }

  return data;
}

export async function listStatements(householdId?: number | null): Promise<StatementLineOut[]> {
  const { data, error, response } = await appApiClient.GET("/billing/statements", {
    params: { query: householdId == null ? {} : { household_id: householdId } },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function getBalance(householdId?: number | null): Promise<BalanceOut> {
  const { data, error, response } = await appApiClient.GET("/billing/balance", {
    params: { query: householdId == null ? {} : { household_id: householdId } },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function listAdjustments(householdId?: number | null): Promise<AdjustmentOut[]> {
  const { data, error, response } = await appApiClient.GET("/billing/adjustments", {
    params: { query: householdId == null ? {} : { household_id: householdId } },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function listMyStatements(): Promise<HouseholdStatementsOut[]> {
  const { data, response } = await appApiClient.GET("/me/statements");

  if (!data) {
    throw buildApiError(response.status, null);
  }

  return data;
}

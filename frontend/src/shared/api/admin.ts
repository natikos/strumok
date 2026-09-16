import type { components } from "./generated/openapi.ts";

import { ApiError, appApiClient, buildApiError } from "./client";

export type AdminUserSummaryOut = components["schemas"]["AdminUserSummaryOut"];
export type AdminHouseholdOut = components["schemas"]["AdminHouseholdOut"];
type AdminHouseholdCreateIn = components["schemas"]["AdminHouseholdCreateIn"];
type HouseholdOwnerAssignIn = components["schemas"]["HouseholdOwnerAssignIn"];

export async function listAdminUsers(): Promise<AdminUserSummaryOut[]> {
  const { data } = await appApiClient.GET("/admin/users");

  return data ?? [];
}

export async function listAdminHouseholds(): Promise<AdminHouseholdOut[]> {
  const { data } = await appApiClient.GET("/admin/households");

  return data ?? [];
}

export async function createAdminHousehold(
  payload: AdminHouseholdCreateIn
): Promise<AdminHouseholdOut> {
  const { data, error, response } = await appApiClient.POST("/admin/households", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export const HOUSEHOLD_ALREADY_ASSIGNED_ERROR_CODE = "householdAlreadyAssigned";

export async function assignAdminHouseholdOwner(
  householdId: number,
  payload: HouseholdOwnerAssignIn
): Promise<AdminHouseholdOut> {
  const { data, error, response } = await appApiClient.PATCH(
    "/admin/households/{household_id}/owner",
    {
      body: payload,
      params: { path: { household_id: householdId } },
    }
  );

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export function isHouseholdAlreadyAssignedError(error: unknown): boolean {
  return error instanceof ApiError && error.message === HOUSEHOLD_ALREADY_ASSIGNED_ERROR_CODE;
}

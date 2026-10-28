import type { components } from "./generated/openapi.ts";

import { ApiError, appApiClient, buildApiError } from "./client";

export type AdminUserOut = components["schemas"]["AdminUserOut"];
export type AdminInviteOut = components["schemas"]["AdminInviteOut"];
export type AdminUserSummaryOut = components["schemas"]["AdminUserSummaryOut"];
export type AdminHouseholdOut = components["schemas"]["AdminHouseholdOut"];
export type AdminDashboardOut = components["schemas"]["AdminDashboardOut"];
export type AuditLogPageOut = components["schemas"]["AuditLogPageOut"];
export type AuditLogEntryOut = components["schemas"]["AuditLogEntryOut"];
type AdminHouseholdCreateIn = components["schemas"]["AdminHouseholdCreateIn"];
type HouseholdOwnerAssignIn = components["schemas"]["HouseholdOwnerAssignIn"];

export async function listAdminUsers(): Promise<AdminUserOut[]> {
  const { data } = await appApiClient.GET("/admin/users");

  return data ?? [];
}

export async function listAdminHouseholds(): Promise<AdminHouseholdOut[]> {
  const { data } = await appApiClient.GET("/admin/households");

  return data ?? [];
}

export async function getAdminDashboard(): Promise<AdminDashboardOut> {
  const { data } = await appApiClient.GET("/admin/dashboard");

  if (!data) {
    throw new Error("Admin dashboard response was empty");
  }

  return data;
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

export async function getAuditLog(query: {
  action?: string;
  cursor?: number;
  household_id?: number;
  period?: string;
}): Promise<AuditLogPageOut> {
  const { data, error, response } = await appApiClient.GET("/admin/audit-log", {
    params: { query },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function updateAdminUser(
  userId: number,
  payload: { is_active?: boolean; is_admin?: boolean; unassign_households?: boolean }
): Promise<AdminUserOut> {
  const { data, error, response } = await appApiClient.PATCH("/admin/users/{user_id}", {
    body: { unassign_households: false, ...payload, confirm: true },
    params: { path: { user_id: userId } },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function updateAdminHousehold(
  householdId: number,
  payload: { is_active?: boolean; name?: string }
): Promise<AdminHouseholdOut> {
  const { data, error, response } = await appApiClient.PATCH("/admin/households/{household_id}", {
    body: { ...payload, confirm: true },
    params: { path: { household_id: householdId } },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function inviteAdminUser(payload: {
  email: string;
  first_name: string;
  household_id?: number;
  language: "en" | "ua";
  last_name: string;
}): Promise<AdminInviteOut> {
  const { data, error, response } = await appApiClient.POST("/admin/users", { body: payload });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function resendAdminInvite(userId: number): Promise<AdminInviteOut> {
  const { data, error, response } = await appApiClient.POST("/admin/users/{user_id}/invite", {
    params: { path: { user_id: userId } },
  });

  if (error) {
    throw buildApiError(response.status, error, response.headers);
  }

  return data;
}

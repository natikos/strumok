import type { components } from "./generated/openapi.ts";

import { setAuthSessionState } from "./auth-session";
import { appApiClient, buildApiError } from "./client";

type LoginIn = components["schemas"]["LoginIn"];
type RegisterIn = components["schemas"]["RegisterIn"];
export type UserOut = components["schemas"]["UserOut"];
type UserPreferencesIn = components["schemas"]["UserPreferencesIn"];

export { ApiError } from "./client";

export async function loginUser(payload: LoginIn): Promise<UserOut> {
  const { data, error, response } = await appApiClient.POST("/auth/login", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  setAuthSessionState(true, data.email_verified);
  return data;
}

export async function registerUser(payload: RegisterIn): Promise<UserOut> {
  const { data, error, response } = await appApiClient.POST("/auth/register", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  setAuthSessionState(true, data.email_verified);
  return data;
}

export async function getMe(): Promise<UserOut> {
  const { data, error, response } = await appApiClient.GET("/auth/me");

  if (error) {
    throw buildApiError(response.status, error);
  }

  setAuthSessionState(true, data.email_verified);

  return data;
}

export async function updateMyPreferences(payload: Partial<UserPreferencesIn>): Promise<UserOut> {
  const { data, error, response } = await appApiClient.PATCH("/auth/preferences", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function logoutUser(): Promise<void> {
  const { response } = await appApiClient.POST("/auth/logout");

  if (!response.ok) {
    throw buildApiError(response.status, undefined);
  }

  setAuthSessionState(false, false);
}

export async function sendVerificationEmailLink(): Promise<void> {
  const { error, response } = await appApiClient.POST("/auth/verification-link");

  if (!response.ok) {
    throw buildApiError(response.status, error);
  }
}

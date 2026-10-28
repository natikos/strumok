import type { components } from "./generated/openapi.ts";

import { setAuthSessionState } from "./auth-session";
import { appApiClient, buildApiError } from "./client";

type LoginIn = components["schemas"]["LoginIn"];
type RegisterIn = components["schemas"]["RegisterIn"];
export type UserOut = components["schemas"]["UserOut"];
export type UserWithHouseholdsOut = components["schemas"]["UserWithHouseholdsOut"];
type UserPreferencesIn = components["schemas"]["UserPreferencesIn"];

export { ApiError } from "./client";

export async function loginUser(payload: LoginIn): Promise<UserOut> {
  const { data, error, response } = await appApiClient.POST("/auth/login", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error, response.headers);
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

export async function getMe(): Promise<UserWithHouseholdsOut> {
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

export async function confirmEmailVerification(token: string): Promise<UserOut> {
  const { data, error, response } = await appApiClient.POST("/auth/verify-email", {
    body: { token },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  setAuthSessionState(true, data.email_verified);
  return data;
}

export async function changePassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  const { error, response } = await appApiClient.POST("/auth/password", { body: payload });

  if (!response.ok) {
    throw buildApiError(response.status, error, response.headers);
  }
}

export async function requestEmailChange(payload: {
  current_password: string;
  new_email: string;
}): Promise<void> {
  const { error, response } = await appApiClient.POST("/auth/email", { body: payload });

  if (!response.ok) {
    throw buildApiError(response.status, error, response.headers);
  }
}

export async function confirmEmailChange(token: string): Promise<void> {
  const { error, response } = await appApiClient.POST("/auth/confirm-email-change", {
    body: { token },
  });

  if (!response.ok) {
    throw buildApiError(response.status, error);
  }

  // Every session is revoked on change, this one included.
  setAuthSessionState(false, false);
}

export async function requestPasswordReset(email: string): Promise<void> {
  const { error, response } = await appApiClient.POST("/auth/password-reset/request", {
    body: { email },
  });

  if (!response.ok) {
    throw buildApiError(response.status, error);
  }
}

export async function confirmPasswordReset(token: string, password: string): Promise<void> {
  const { error, response } = await appApiClient.POST("/auth/password-reset/confirm", {
    body: { password, token },
  });

  if (!response.ok) {
    throw buildApiError(response.status, error);
  }
}

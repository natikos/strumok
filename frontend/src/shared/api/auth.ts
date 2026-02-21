import type { components } from "./generated/openapi.ts";

import { markAuthenticatedInCache } from "./auth-session";
import { appApiClient, buildApiError } from "./client";

type LoginIn = components["schemas"]["LoginIn"];
type RegisterIn = components["schemas"]["RegisterIn"];
type UserOut = components["schemas"]["UserOut"];

export { ApiError } from "./client";

export async function loginUser(payload: LoginIn): Promise<UserOut> {
  const { data, error, response } = await appApiClient.POST("/auth/login", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  markAuthenticatedInCache();
  return data;
}

export async function registerUser(payload: RegisterIn): Promise<UserOut> {
  const { data, error, response } = await appApiClient.POST("/auth/register", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  markAuthenticatedInCache();
  return data;
}

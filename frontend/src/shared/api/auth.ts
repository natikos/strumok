import type { components } from "./generated/openapi.ts";

import { apiClient, buildApiError } from "./client";

type LoginIn = components["schemas"]["LoginIn"];
type RegisterIn = components["schemas"]["RegisterIn"];
type UserOut = components["schemas"]["UserOut"];

export { ApiError } from "./client";

export async function loginUser(payload: LoginIn): Promise<UserOut> {
  const { data, error, response } = await apiClient.POST("/auth/login", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

export async function registerUser(payload: RegisterIn): Promise<UserOut> {
  const { data, error, response } = await apiClient.POST("/auth/register", {
    body: payload,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }

  return data;
}

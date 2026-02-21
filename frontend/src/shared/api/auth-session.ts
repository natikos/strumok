import { authApiClient } from "./client";

export async function isAuthenticated(): Promise<boolean> {
  try {
    let { response } = await authApiClient.GET("/auth/me");

    if (response.ok) {
      return true;
    }

    if (response.status !== 401) {
      return false;
    }

    const { response: refreshResponse } = await authApiClient.POST("/auth/refresh");

    if (!refreshResponse.ok) {
      return false;
    }

    ({ response } = await authApiClient.GET("/auth/me"));

    return response.ok;
  } catch {
    return false;
  }
}

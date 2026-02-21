import { authApiClient } from "./client";

const AUTH_CHECK_CACHE_TTL_MS = 90_000;
let cachedAuthState: boolean | null = null;
let cachedAt = 0;
let pendingAuthCheck: Promise<boolean> | null = null;

function setCachedAuthState(isAuthenticated: boolean): void {
  cachedAuthState = isAuthenticated;
  cachedAt = Date.now();
}

export function invalidateAuthSessionCache(): void {
  cachedAuthState = null;
  cachedAt = 0;
}

export function markAuthenticatedInCache(): void {
  setCachedAuthState(true);
}

export function markGuestInCache(): void {
  setCachedAuthState(false);
}

async function checkAuthenticationFromServer(): Promise<boolean> {
  try {
    let { response } = await authApiClient.GET("/auth/me");

    if (response.ok) {
      markAuthenticatedInCache();
      return true;
    }

    if (response.status !== 401) {
      markGuestInCache();
      return false;
    }

    const { response: refreshResponse } = await authApiClient.POST("/auth/refresh");

    if (!refreshResponse.ok) {
      markGuestInCache();
      return false;
    }

    ({ response } = await authApiClient.GET("/auth/me"));

    setCachedAuthState(response.ok);
    return response.ok;
  } catch {
    markGuestInCache();
    return false;
  } finally {
    pendingAuthCheck = null;
  }
}

export async function isAuthenticated(): Promise<boolean> {
  if (cachedAuthState !== null && Date.now() - cachedAt < AUTH_CHECK_CACHE_TTL_MS) {
    return cachedAuthState;
  }

  if (pendingAuthCheck) {
    return pendingAuthCheck;
  }

  pendingAuthCheck = checkAuthenticationFromServer();

  return pendingAuthCheck;
}

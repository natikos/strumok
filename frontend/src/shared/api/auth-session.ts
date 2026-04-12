import { authApiClient } from "./client";

interface AuthSessionState {
  isAuthenticated: boolean;
  isEmailVerified: boolean;
}

const UNAUTHENTICATED_STATE: AuthSessionState = {
  isAuthenticated: false,
  isEmailVerified: false,
};

let authState: AuthSessionState = UNAUTHENTICATED_STATE;

export function getAuthSessionState(): AuthSessionState {
  return authState;
}

export function setAuthSessionState(isAuthenticated: boolean, isEmailVerified: boolean): void {
  authState = isAuthenticated ? { isAuthenticated, isEmailVerified } : UNAUTHENTICATED_STATE;
}

export async function initAuthSession(): Promise<AuthSessionState> {
  authState = await fetchAuthState().catch(() => UNAUTHENTICATED_STATE);
  return authState;
}

async function fetchMe(): Promise<AuthSessionState> {
  const { data, response } = await authApiClient.GET("/auth/me");

  return response.ok && data
    ? { isAuthenticated: true, isEmailVerified: data.email_verified }
    : UNAUTHENTICATED_STATE;
}

async function fetchAuthState(): Promise<AuthSessionState> {
  const state = await fetchMe();

  if (state.isAuthenticated) {
    return state;
  }

  const { response } = await authApiClient.POST("/auth/refresh");

  return response.ok ? fetchMe() : UNAUTHENTICATED_STATE;
}

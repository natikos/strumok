import { authApiClient } from "./client";

interface AuthSessionState {
  isAuthenticated: boolean;
  isEmailVerified: boolean;
}

const UNAUTHENTICATED_STATE: AuthSessionState = {
  isAuthenticated: false,
  isEmailVerified: false,
};

// The server couldn't be reached, so the session is kept: the layout shows an
// offline screen with a retry instead of sending the resident to login.
const UNREACHABLE_STATE: AuthSessionState = {
  isAuthenticated: true,
  isEmailVerified: true,
};

class ServerUnreachableError extends Error {}

let authState: AuthSessionState = UNAUTHENTICATED_STATE;

export function getAuthSessionState(): AuthSessionState {
  return authState;
}

export function setAuthSessionState(isAuthenticated: boolean, isEmailVerified: boolean): void {
  authState = isAuthenticated ? { isAuthenticated, isEmailVerified } : UNAUTHENTICATED_STATE;
}

export async function initAuthSession(): Promise<AuthSessionState> {
  authState = await fetchAuthState().catch(() => UNREACHABLE_STATE);
  return authState;
}

// Any 4xx means logged out; a network error (thrown by fetch) or a 5xx means
// the server is unreachable, so the caller keeps the session.
function throwIfUnreachable(response: Response): void {
  if (response.status >= 500) {
    throw new ServerUnreachableError();
  }
}

async function fetchMe(): Promise<AuthSessionState> {
  const { data, response } = await authApiClient.GET("/auth/me");

  if (response.ok && data) {
    return { isAuthenticated: true, isEmailVerified: data.email_verified };
  }

  throwIfUnreachable(response);
  return UNAUTHENTICATED_STATE;
}

async function fetchAuthState(): Promise<AuthSessionState> {
  const state = await fetchMe();

  if (state.isAuthenticated) {
    return state;
  }

  const { response } = await authApiClient.POST("/auth/refresh");

  if (response.ok) {
    return fetchMe();
  }

  throwIfUnreachable(response);
  return UNAUTHENTICATED_STATE;
}

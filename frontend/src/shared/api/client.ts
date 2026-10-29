import createClient from "openapi-fetch";

import type { paths } from "./generated/openapi.ts";

import { showApiErrorToast } from "./error-toast";

// A built app is served by FastAPI from the same origin; only `bun run dev`
// (Vite on :5173) talks to a separate backend.
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");
const REFRESH_ENDPOINT_PATH = "/auth/refresh";

// "rejected" is the server refusing the session (expired, revoked);
// "unreachable" is a network failure, which must not log the resident out.
type RefreshOutcome = "refreshed" | "rejected" | "unreachable";

let refreshPromise: Promise<RefreshOutcome> | null = null;
// Returns true when it ended a signed-in session.
let sessionExpiredHandler: (() => boolean) | null = null;

// Bumped each time a signed-in session ends. A 401 on a request sent before
// that is muted, since the redirect to login already tells the resident; one
// sent after (a wrong password on the login page) still toasts.
let sessionEpoch = 0;
const requestEpochs = new Map<string, number>();

// Registered by main.ts, which owns the router; the client can't import it
// without a cycle.
export function registerSessionExpiredHandler(handler: () => boolean): void {
  sessionExpiredHandler = handler;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly retryAfterSeconds: number | undefined;

  constructor(message: string, status: number, retryAfterSeconds?: number) {
    super(message);
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

// Sent on every request so a mutating one always forces a CORS preflight --
// a plain cross-site HTML form can't set a custom header, so its POST never
// carries this and the backend's CsrfMiddleware rejects it (see #147).
const CSRF_HEADERS = { "X-Requested-With": "XMLHttpRequest" };

// Main API client for app requests: includes middleware (refresh, retry, global error toasts).
export const appApiClient = createClient<paths>({
  baseUrl: API_BASE_URL,
  headers: CSRF_HEADERS,
  fetch: (request) => fetch(request, { credentials: "include" }),
});

// Internal auth client: no middleware to avoid recursive refresh/retry loops.
export const authApiClient = createClient<paths>({
  baseUrl: API_BASE_URL,
  headers: CSRF_HEADERS,
  fetch: (request) => fetch(request, { credentials: "include" }),
});

async function refreshAccessToken(): Promise<RefreshOutcome> {
  if (!refreshPromise) {
    refreshPromise = authApiClient
      .POST(REFRESH_ENDPOINT_PATH)
      .then(({ response }): RefreshOutcome => {
        if (response.ok) {
          return "refreshed";
        }

        return response.status < 500 ? "rejected" : "unreachable";
      })
      .catch((): RefreshOutcome => "unreachable")
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

appApiClient.use({
  onRequest({ id, request }) {
    requestEpochs.set(id, sessionEpoch);
    return new Request(request, { credentials: "include" });
  },
  onError({ id }) {
    requestEpochs.delete(id);
  },
  async onResponse({ id, request, response }) {
    const requestEpoch = requestEpochs.get(id) ?? sessionEpoch;
    requestEpochs.delete(id);
    let effectiveResponse = response;
    const requestPath = new URL(request.url).pathname;
    const isRefreshRequest = requestPath.endsWith(REFRESH_ENDPOINT_PATH);

    if (effectiveResponse.status === 401 && !isRefreshRequest) {
      const outcome = await refreshAccessToken();

      if (outcome === "refreshed") {
        effectiveResponse = await fetch(new Request(request, { credentials: "include" }));
      } else if (outcome === "rejected" && sessionExpiredHandler?.()) {
        sessionEpoch += 1;
      }
    }

    if (effectiveResponse.ok) {
      return effectiveResponse;
    }

    let body: unknown;

    try {
      body = await effectiveResponse.clone().json();
    } catch {
      body = undefined;
    }

    if (effectiveResponse.status !== 401 || requestEpoch === sessionEpoch) {
      showApiErrorToast(effectiveResponse.status, body);
    }

    return effectiveResponse;
  },
});

export function buildApiError(status: number, body: unknown, headers?: Headers): ApiError {
  const detailValue =
    body && typeof body === "object" && "detail" in body ? body.detail : undefined;
  const detail =
    typeof detailValue === "string" ? detailValue : `Request failed with status ${status}`;

  const retryAfter = Number(headers?.get("Retry-After"));

  return new ApiError(
    detail,
    status,
    Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : undefined
  );
}

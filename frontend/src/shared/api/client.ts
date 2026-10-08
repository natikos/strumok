import createClient from "openapi-fetch";

import type { paths } from "./generated/openapi.ts";

import { showApiErrorToast } from "./error-toast";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const REFRESH_ENDPOINT_PATH = "/auth/refresh";

let refreshPromise: Promise<boolean> | null = null;

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

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = authApiClient
      .POST(REFRESH_ENDPOINT_PATH)
      .then(({ response }) => response.ok)
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

appApiClient.use({
  onRequest({ request }) {
    return new Request(request, { credentials: "include" });
  },
  async onResponse({ request, response }) {
    let effectiveResponse = response;
    const requestPath = new URL(request.url).pathname;
    const isRefreshRequest = requestPath.endsWith(REFRESH_ENDPOINT_PATH);

    if (effectiveResponse.status === 401 && !isRefreshRequest) {
      const isRefreshed = await refreshAccessToken();

      if (isRefreshed) {
        effectiveResponse = await fetch(new Request(request, { credentials: "include" }));
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

    showApiErrorToast(effectiveResponse.status, body);

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

import createClient from "openapi-fetch";

import type { paths } from "./generated/openapi.ts";

import { showApiErrorToast } from "./error-toast";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  public readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export const apiClient = createClient<paths>({
  baseUrl: API_BASE_URL,
  fetch: (request) => fetch(request, { credentials: "include" }),
});

apiClient.use({
  onRequest({ request }) {
    return new Request(request, { credentials: "include" });
  },
  async onResponse({ response }) {
    if (response.ok) {
      return response;
    }

    let body: unknown;

    try {
      body = await response.clone().json();
    } catch {
      body = undefined;
    }

    showApiErrorToast(response.status, body);

    return response;
  },
});

export function buildApiError(status: number, body: unknown): ApiError {
  const detailValue =
    body && typeof body === "object" && "detail" in body ? body.detail : undefined;
  const detail =
    typeof detailValue === "string" ? detailValue : `Request failed with status ${status}`;

  return new ApiError(detail, status);
}

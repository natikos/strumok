import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { registerToastPresenter } from "./error-toast";

/**
 * Exercises appApiClient's 401 -> refresh -> retry-once middleware
 * (src/shared/api/client.ts). Mocked at `fetch`, the network boundary the repo
 * convention calls for, so the middleware's actual Request/Response handling is
 * under test rather than a stand-in for it.
 *
 * `appApiClient` is a module-level singleton with module-level `refreshPromise`
 * state, so each test re-imports the module fresh via `vi.resetModules()` to stop
 * one test's in-flight refresh state leaking into the next.
 */

function jsonResponse(status: number, body?: unknown): Response {
  if (status === 204 || body === undefined) {
    return new Response(null, { status });
  }

  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function loadClient() {
  vi.resetModules();
  return import("./client");
}

describe("appApiClient 401 refresh-and-retry middleware", () => {
  beforeEach(() => {
    registerToastPresenter(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("retries the original request once after a successful refresh", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "invalidOrExpiredToken" }))
      .mockResolvedValueOnce(jsonResponse(204)) // POST /auth/refresh
      .mockResolvedValueOnce(jsonResponse(200, { id: 1, email: "resident@example.com" }));
    vi.stubGlobal("fetch", fetchMock);

    const { appApiClient } = await loadClient();
    const { response, data } = await appApiClient.GET("/auth/me");

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(response.status).toBe(200);
    expect(data).toEqual({ id: 1, email: "resident@example.com" });

    const refreshCall = fetchMock.mock.calls[1][0] as Request;
    expect(new URL(refreshCall.url).pathname).toBe("/auth/refresh");
  });

  it("returns the original 401 without retrying when refresh itself fails", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "invalidOrExpiredToken" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "missingAuthenticationToken" })); // refresh fails
    vi.stubGlobal("fetch", fetchMock);

    const { appApiClient } = await loadClient();
    const { response } = await appApiClient.GET("/auth/me");

    // Exactly the original request + the refresh attempt: no retry, no loop.
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(401);
  });

  it("dedupes concurrent 401s from different requests into a single refresh call", async () => {
    let refreshCalls = 0;
    // Track how many times each distinct request path has been seen so the
    // second occurrence (the retry) can be told apart from the first (the
    // original, which 401s) without relying on request headers/order.
    const seenCounts = new Map<string, number>();

    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const request = input as Request;
      const pathname = new URL(request.url).pathname;

      if (pathname === "/auth/refresh") {
        refreshCalls += 1;
        return Promise.resolve(jsonResponse(204));
      }

      const seenSoFar = seenCounts.get(pathname) ?? 0;
      seenCounts.set(pathname, seenSoFar + 1);

      // First hit on this path -> unauthorized; the retry after refresh succeeds.
      return Promise.resolve(
        seenSoFar === 0 ? jsonResponse(401) : jsonResponse(200, { path: pathname })
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { appApiClient } = await loadClient();

    const [first, second] = await Promise.all([
      appApiClient.GET("/auth/me"),
      appApiClient.GET("/meter-readings" as never),
    ]);

    expect(refreshCalls).toBe(1);
    expect(first.response.status).toBe(200);
    expect(second.response.status).toBe(200);
  });

  it("never triggers a nested refresh when the refresh request itself returns 401", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(401));
    vi.stubGlobal("fetch", fetchMock);

    const { authApiClient } = await loadClient();
    const { response } = await authApiClient.POST("/auth/refresh");

    // authApiClient carries no middleware at all, so a 401 here must not
    // trigger any further fetch beyond the single call made.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(401);
  });
});

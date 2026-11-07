import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { logoutUser as logoutUserType } from "./auth";
import type { getAuthSessionState as getAuthSessionStateType } from "./auth-session";

const { POST } = vi.hoisted(() => ({ POST: vi.fn() }));

// `isolate: false` shares the module cache, so evaluate against the mock fresh
// (see auth-session.test.ts).
let logoutUser: typeof logoutUserType;
let getAuthSessionState: typeof getAuthSessionStateType;
let setAuthSessionState: (isAuthenticated: boolean, isEmailVerified: boolean) => void;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("./client", async (importOriginal) => ({
    ...(await importOriginal<Record<string, unknown>>()),
    appApiClient: { POST },
  }));
  ({ logoutUser } = await import("./auth"));
  ({ getAuthSessionState, setAuthSessionState } = await import("./auth-session"));
});

afterAll(() => {
  vi.doUnmock("./client");
  vi.resetModules();
});

describe("logoutUser", () => {
  beforeEach(() => {
    POST.mockReset();
    localStorage.clear();
    setAuthSessionState(true, true);
  });

  it("signs out locally and remembers to finish on the server when offline", async () => {
    POST.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(logoutUser()).resolves.toBeUndefined();

    expect(getAuthSessionState().isAuthenticated).toBe(false);
    expect(localStorage.getItem("strumok:pending-logout")).not.toBeNull();
  });

  it("still surfaces a server error without signing out", async () => {
    POST.mockResolvedValue({ response: new Response(null, { status: 500 }) });

    await expect(logoutUser()).rejects.toBeDefined();

    expect(getAuthSessionState().isAuthenticated).toBe(true);
    expect(localStorage.getItem("strumok:pending-logout")).toBeNull();
  });
});

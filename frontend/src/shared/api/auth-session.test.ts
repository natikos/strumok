import { beforeEach, describe, expect, it, vi } from "vitest";

const { GET, POST } = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn() }));

vi.mock("./client", () => ({ authApiClient: { GET, POST } }));

import { initAuthSession } from "./auth-session";

function respond(status: number, data?: unknown) {
  return { data, response: new Response(null, { status }) };
}

describe("initAuthSession", () => {
  beforeEach(() => {
    GET.mockReset();
    POST.mockReset();
  });

  it("keeps the session when the network fails", async () => {
    GET.mockRejectedValue(new TypeError("Failed to fetch"));

    expect(await initAuthSession()).toEqual({ isAuthenticated: true, isEmailVerified: true });
  });

  it("keeps the session when the server returns 5xx", async () => {
    GET.mockResolvedValue(respond(503));

    expect((await initAuthSession()).isAuthenticated).toBe(true);
  });

  it("logs out when /auth/me and the refresh are rejected", async () => {
    GET.mockResolvedValue(respond(401));
    POST.mockResolvedValue(respond(401));

    expect((await initAuthSession()).isAuthenticated).toBe(false);
  });

  it("re-reads /auth/me after a successful refresh", async () => {
    GET.mockResolvedValueOnce(respond(401)).mockResolvedValueOnce(
      respond(200, { email_verified: false })
    );
    POST.mockResolvedValue(respond(200));

    expect(await initAuthSession()).toEqual({ isAuthenticated: true, isEmailVerified: false });
  });
});

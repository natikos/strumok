import { type APIRequestContext, test as base, expect } from "@playwright/test";

const CSRF_HEADERS = { "X-Requested-With": "XMLHttpRequest" };

export interface SeededUser {
  id: number;
  email: string;
  password: string;
  firstName: string;
  lastName: string;
}

export interface SeedUserOptions {
  isAdmin?: boolean;
  email?: string;
  password?: string;
  firstName?: string;
  lastName?: string;
}

export interface OutboxMessage {
  to: string;
  subject: string;
  html_content: string;
}

interface Fixtures {
  /** Unauthenticated API context for the e2e-only endpoints; always sends the CSRF header. */
  api: APIRequestContext;
  /** A new API context signed in as `user`, for seeding through the real admin API. */
  apiAs: (user: SeededUser) => Promise<APIRequestContext>;
  /**
   * Moves the backend clock and the browser clock to the same instant. Call it
   * before the first `page.goto` and before logging anyone in. `iso` must carry
   * an offset, e.g. "2026-07-02T12:00:00+03:00".
   */
  setNow: (iso: string) => Promise<void>;
  seedUser: (options?: SeedUserOptions) => Promise<SeededUser>;
  /** Signs in through the API so the cookie lands in the page's browser context. */
  loginAs: (user: SeededUser) => Promise<void>;
  readOutbox: (to: string) => Promise<OutboxMessage[]>;
  resetBackend: void;
  englishUi: void;
}

let userCounter = 0;

export const test = base.extend<Fixtures>({
  api: async ({ playwright, baseURL }, use) => {
    const context = await playwright.request.newContext({
      baseURL: baseURL ?? "",
      extraHTTPHeaders: CSRF_HEADERS,
    });
    await use(context);
    await context.dispose();
  },

  resetBackend: [
    async ({ api }, use) => {
      const response = await api.post("/__e2e/reset");
      expect(response.status(), await response.text()).toBe(204);
      await use();
    },
    { auto: true },
  ],

  // The app ignores the browser locale and starts in Ukrainian on a fresh
  // device, so seed the stored preference the app itself reads.
  englishUi: [
    async ({ page }, use) => {
      await page.addInitScript(() => {
        window.localStorage.setItem("strumok:user-preferences", JSON.stringify({ language: "en" }));
      });
      await use();
    },
    { auto: true },
  ],

  apiAs: async ({ playwright, baseURL }, use) => {
    const contexts: APIRequestContext[] = [];
    await use(async (user) => {
      const context = await playwright.request.newContext({
        baseURL: baseURL ?? "",
        extraHTTPHeaders: CSRF_HEADERS,
      });
      contexts.push(context);
      const response = await context.post("/auth/login", {
        data: { email: user.email, password: user.password },
      });
      expect(response.status(), await response.text()).toBe(200);
      return context;
    });
    await Promise.all(contexts.map((context) => context.dispose()));
  },

  setNow: async ({ api, page }, use) => {
    await use(async (iso) => {
      const time = new Date(iso);
      expect(Number.isNaN(time.getTime()), `unparseable time ${iso}`).toBe(false);
      expect(iso, "the time needs an explicit UTC offset").toMatch(/(Z|[+-]\d{2}:?\d{2})$/);
      const response = await api.put("/__e2e/clock", { data: { now: iso } });
      expect(response.status(), await response.text()).toBe(200);
      await page.clock.install({ time });
    });
  },

  seedUser: async ({ api }, use) => {
    await use(async (options = {}) => {
      userCounter += 1;
      const user: SeededUser = {
        id: 0,
        email: options.email ?? `user${userCounter}@example.com`,
        password: options.password ?? "e2e-password-123",
        firstName: options.firstName ?? "Test",
        lastName: options.lastName ?? `User${userCounter}`,
      };
      const response = await api.post("/__e2e/users", {
        data: {
          email: user.email,
          password: user.password,
          first_name: user.firstName,
          last_name: user.lastName,
          is_admin: options.isAdmin ?? false,
          language: "en",
        },
      });
      expect(response.status(), await response.text()).toBe(201);
      user.id = ((await response.json()) as { id: number }).id;
      return user;
    });
  },

  loginAs: async ({ page }, use) => {
    await use(async (user) => {
      const response = await page.request.post("/auth/login", {
        data: { email: user.email, password: user.password },
        headers: CSRF_HEADERS,
      });
      expect(response.status(), await response.text()).toBe(200);
    });
  },

  readOutbox: async ({ api }, use) => {
    await use(async (to) => {
      const response = await api.get("/__e2e/outbox", { params: { to } });
      expect(response.status(), await response.text()).toBe(200);
      return (await response.json()) as OutboxMessage[];
    });
  },
});

export { expect };

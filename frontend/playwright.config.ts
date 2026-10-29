import { defineConfig, devices } from "@playwright/test";

const PORT = 8787;
const ORIGIN = `http://localhost:${PORT}`;
const isCI = Boolean(process.env["CI"]);

// Every setting the backend reads is spelled out: backend/.env points at a
// remote database and pydantic-settings would otherwise fill any gap from it.
const serverEnv: Record<string, string> = {
  ENVIRONMENT: "e2e",
  DATABASE_URL:
    process.env["E2E_DATABASE_URL"] ?? "postgresql://postgres:postgres@localhost:5432/strumok_e2e",
  AUTH_SECRET_KEY: "e2e-only",
  PUSH_VAPID_PUBLIC_KEY: "e2e-vapid-public-key",
  PUSH_VAPID_PRIVATE_KEY: "e2e-vapid-private-key",
  PUSH_VAPID_SUBJECT: "mailto:e2e@example.com",
  BREVO_API_KEY: "",
  BREVO_SENDER_EMAIL: "",
  BREVO_APP_BASE_URL: ORIGIN,
  IMAP_USER: "",
  IMAP_PASSWORD: "",
  IMAP_ALLOWED_SENDERS: "",
  CORS_ORIGINS: ORIGIN,
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: ORIGIN,
    locale: "en-US",
    timezoneId: "Europe/Kyiv",
    viewport: { width: 360, height: 740 },
    serviceWorkers: "block",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 740 } },
    },
  ],
  webServer: {
    command:
      "cd ../backend && uv run python scripts/e2e_prepare_db.py && uv run uvicorn app.main:app --host 127.0.0.1 --port 8787 --workers 1",
    url: "http://127.0.0.1:8787/health",
    reuseExistingServer: false,
    timeout: 120_000,
    env: serverEnv,
  },
});

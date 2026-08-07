import { afterEach, vi } from "vitest";

// Global teardown so individual specs don't each have to remember it. Leaked fake
// timers or unrestored mocks surface as failures in an unrelated later test, which
// is a miserable thing to debug.
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

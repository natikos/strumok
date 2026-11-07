import { disableAutoUnmount, enableAutoUnmount } from "@vue/test-utils";
import { afterEach, beforeEach, vi } from "vitest";

// Unmount wrappers after every test so a mounted component never keeps reacting to
// state (e.g. the current-household singleton) changed by a later test in the file.
// This setup file re-runs per spec file against the same cached test-utils module,
// which allows only one `enableAutoUnmount`, so reset it first.
disableAutoUnmount();
enableAutoUnmount(afterEach);

// Global teardown so individual specs don't each have to remember it. Leaked fake
// timers or unrestored mocks surface as failures in an unrelated later test, which
// is a miserable thing to debug.
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

// Pin the wall clock (Date only, so promises and timers keep running) to a mid-month
// instant outside the day 1-5 submit window. Specs that care about a particular day
// call `vi.setSystemTime` themselves; the rest no longer change behaviour with the
// calendar day the suite happens to run on.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-07-15T09:00:00.000Z"));
});

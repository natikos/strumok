import { disableAutoUnmount, enableAutoUnmount } from "@vue/test-utils";
import { afterEach, vi } from "vitest";

// `isolate: false` shares module state (e.g. the current-household singleton) across
// spec files, so a wrapper left mounted by one file keeps reacting to another file's
// state changes and throws from its watchers. Unmount after every test. This setup
// file re-runs per spec file against the same cached test-utils module, which allows
// only one `enableAutoUnmount`, so reset it first.
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

import { afterEach, describe, expect, it, vi } from "vitest";

import { registerToastPresenter, showApiErrorToast } from "./error-toast";

/**
 * `getStatusMessageKey` and `toErrorMessageKey` aren't exported -- they're
 * exercised here through `showApiErrorToast`'s payload, which is the only
 * observable surface of the pure mapping logic without reaching into the
 * side-effecting presenter registration itself.
 */
describe("error-toast status-to-message-key mapping", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("maps 401 to the unauthorized key", () => {
    const presenter = vi.fn();
    registerToastPresenter(presenter);

    showApiErrorToast(401, null);

    expect(presenter).toHaveBeenCalledWith(
      expect.objectContaining({ fallbackMessageKey: "errors.unauthorized" })
    );
  });

  it("maps 422 to the validation error key", () => {
    const presenter = vi.fn();
    registerToastPresenter(presenter);

    showApiErrorToast(422, null);

    expect(presenter).toHaveBeenCalledWith(
      expect.objectContaining({ fallbackMessageKey: "errors.validationError" })
    );
  });

  it("maps 429 to the too-many-requests key", () => {
    const presenter = vi.fn();
    registerToastPresenter(presenter);

    showApiErrorToast(429, null);

    expect(presenter).toHaveBeenCalledWith(
      expect.objectContaining({ fallbackMessageKey: "errors.tooManyRequests" })
    );
  });

  it("maps 500 to the server error key", () => {
    const presenter = vi.fn();
    registerToastPresenter(presenter);

    showApiErrorToast(500, null);

    expect(presenter).toHaveBeenCalledWith(
      expect.objectContaining({ fallbackMessageKey: "errors.serverError" })
    );
  });

  it("falls back to a generic request-failed key for an unmapped status", () => {
    const presenter = vi.fn();
    registerToastPresenter(presenter);

    showApiErrorToast(418, null);

    expect(presenter).toHaveBeenCalledWith(
      expect.objectContaining({ fallbackMessageKey: "errors.requestFailed" })
    );
  });

  it("prefers the backend's stable detail code over the status fallback", () => {
    const presenter = vi.fn();
    registerToastPresenter(presenter);

    showApiErrorToast(403, { detail: "householdNotAccessible" });

    expect(presenter).toHaveBeenCalledWith(
      expect.objectContaining({ messageKey: "errors.householdNotAccessible" })
    );
  });

  it("falls back to the status-derived key when the body has no string detail", () => {
    const presenter = vi.fn();
    registerToastPresenter(presenter);

    showApiErrorToast(500, { detail: 42 });

    expect(presenter).toHaveBeenCalledWith(
      expect.objectContaining({ messageKey: "errors.serverError" })
    );
  });

  it("falls back to the status-derived key when the body is null", () => {
    const presenter = vi.fn();
    registerToastPresenter(presenter);

    showApiErrorToast(500, null);

    expect(presenter).toHaveBeenCalledWith(
      expect.objectContaining({ messageKey: "errors.serverError" })
    );
  });

  it("does nothing when no presenter has been registered", () => {
    // registerToastPresenter's unregister function from the previous test's
    // cleanup would leave this null, but be explicit: unregister here too.
    const presenter = vi.fn();
    const unregister = registerToastPresenter(presenter);
    unregister();

    expect(() => showApiErrorToast(500, null)).not.toThrow();
    expect(presenter).not.toHaveBeenCalled();
  });
});

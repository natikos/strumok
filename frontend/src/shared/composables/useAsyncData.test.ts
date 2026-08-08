import { describe, expect, it, vi } from "vitest";

import { useAsyncData } from "./useAsyncData";

describe("useAsyncData", () => {
  describe("initial state", () => {
    it("starts loading and with no data or error when immediate", () => {
      const asyncFn = vi.fn().mockResolvedValue("value");
      const { data, isLoading, error } = useAsyncData(asyncFn);

      expect(isLoading.value).toBe(true);
      expect(data.value).toBeNull();
      expect(error.value).toBeNull();
    });

    it("does not start loading or call the function when immediate is false", () => {
      const asyncFn = vi.fn().mockResolvedValue("value");
      const { isLoading } = useAsyncData(asyncFn, false);

      expect(isLoading.value).toBe(false);
      expect(asyncFn).not.toHaveBeenCalled();
    });
  });

  describe("successful execute", () => {
    it("populates data and resets loading once the promise resolves", async () => {
      const asyncFn = vi.fn().mockResolvedValue({ id: 1 });
      const { data, isLoading, execute } = useAsyncData(asyncFn, false);

      const promise = execute();
      expect(isLoading.value).toBe(true);

      await promise;

      expect(isLoading.value).toBe(false);
      expect(data.value).toEqual({ id: 1 });
    });

    it("clears a previous error when a subsequent execute succeeds", async () => {
      const asyncFn = vi
        .fn()
        .mockRejectedValueOnce(new Error("first failure"))
        .mockResolvedValueOnce("recovered");
      const { data, error, execute } = useAsyncData(asyncFn, false);

      await execute();
      expect(error.value).not.toBeNull();

      await execute();
      expect(error.value).toBeNull();
      expect(data.value).toBe("recovered");
    });
  });

  describe("failed execute", () => {
    it("captures a thrown Error instance and resets loading", async () => {
      const failure = new Error("network down");
      const asyncFn = vi.fn().mockRejectedValue(failure);
      const { data, isLoading, error, execute } = useAsyncData(asyncFn, false);

      await execute();

      expect(isLoading.value).toBe(false);
      expect(error.value).toBe(failure);
      expect(data.value).toBeNull();
    });

    it("wraps a non-Error rejection in an Error rather than storing it raw", async () => {
      const asyncFn = vi.fn().mockRejectedValue("string failure");
      const { error, execute } = useAsyncData(asyncFn, false);

      await execute();

      expect(error.value).toBeInstanceOf(Error);
      expect(error.value?.message).toBe("string failure");
    });

    it("leaves previously loaded data in place after a later execute fails", async () => {
      // A household's most recent successful fetch shouldn't be wiped out just
      // because a subsequent refresh attempt failed -- the resident should
      // still see their last known data, with the error surfaced alongside it.
      const asyncFn = vi
        .fn()
        .mockResolvedValueOnce("first value")
        .mockRejectedValueOnce(new Error("refresh failed"));
      const { data, error, execute } = useAsyncData(asyncFn, false);

      await execute();
      expect(data.value).toBe("first value");

      await execute();
      expect(error.value).not.toBeNull();
      expect(data.value).toBe("first value");
    });
  });

  describe("re-execution", () => {
    it("calls the async function again on each execute", async () => {
      const asyncFn = vi.fn().mockResolvedValue("value");
      const { execute } = useAsyncData(asyncFn, false);

      await execute();
      await execute();
      await execute();

      expect(asyncFn).toHaveBeenCalledTimes(3);
    });
  });
});

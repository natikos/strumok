import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";

import { usePushNotifications } from "./usePushNotifications";

/**
 * Unit tests for the `usePushNotifications` state machine.
 *
 * Strategy: the composable is pure orchestration on top of two collaborators:
 *   - `./web-push`          (browser Push API wrappers)
 *   - `@/shared/api/push`   (backend API)
 * Both are mocked, so these tests verify the composable's own decisions:
 * which state it reports, in which order it calls collaborators, and how it
 * rolls back when a step fails. Browser-level behaviour (UA sniffing, feature
 * detection, base64 decoding) belongs in `web-push.test.ts`.
 *
 * `Notification` is the only browser global the composable reads directly, so
 * it is the only one stubbed here.
 */

const api = vi.hoisted(() => ({
  getVapidPublicKey: vi.fn(),
  subscribeToPush: vi.fn(),
  unsubscribeFromPush: vi.fn(),
}));

const webPush = vi.hoisted(() => ({
  base64ToUint8Array: vi.fn(),
  getWebPushSubscription: vi.fn(),
  isIosNotInstalled: vi.fn(),
  isPushSupported: vi.fn(),
  subscribeToWebPush: vi.fn(),
  unsubscribeFromWebPush: vi.fn(),
}));

vi.mock("@/shared/api/push", () => api);
vi.mock("./web-push", () => webPush);

const APP_SERVER_KEY = new Uint8Array([1, 2, 3, 4]);
const BROWSER_SUBSCRIPTION = {
  endpoint: "https://push.example.com/new",
  keys: { auth: "a-key", p256dh: "p-key" },
};

/** Minimal controllable stand-in for the global `Notification`. */
function stubNotification(
  initial: NotificationPermission,
  onRequest: NotificationPermission = initial
) {
  const stub = {
    permission: initial,
    requestPermission: vi.fn(() => {
      // A real browser updates `Notification.permission` when the user answers.
      stub.permission = onRequest;
      return Promise.resolve(onRequest);
    }),
  };
  vi.stubGlobal("Notification", stub);
  return stub;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, reject, resolve };
}

const wrappers: VueWrapper[] = [];

function mountComposable() {
  let result!: ReturnType<typeof usePushNotifications>;
  const Harness = defineComponent({
    setup() {
      result = usePushNotifications();
      return () => h("div");
    },
  });
  wrappers.push(mount(Harness));
  return result;
}

/** Mounts and waits for the on-mount `refreshState()` to settle. */
async function mountSettled() {
  const result = mountComposable();
  await flushPromises();
  return result;
}

beforeEach(() => {
  vi.resetAllMocks();

  // Happy-path defaults; each test overrides only what it cares about.
  webPush.isPushSupported.mockReturnValue(true);
  webPush.isIosNotInstalled.mockReturnValue(false);
  webPush.getWebPushSubscription.mockResolvedValue(null);
  webPush.base64ToUint8Array.mockReturnValue(APP_SERVER_KEY);
  webPush.subscribeToWebPush.mockResolvedValue(BROWSER_SUBSCRIPTION);
  webPush.unsubscribeFromWebPush.mockResolvedValue("https://push.example.com/existing");
  api.getVapidPublicKey.mockResolvedValue("vapid-public-key");
  api.subscribeToPush.mockResolvedValue(undefined);
  api.unsubscribeFromPush.mockResolvedValue(undefined);

  stubNotification("default");
});

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  vi.unstubAllGlobals();
});

describe("usePushNotifications", () => {
  describe("initial state", () => {
    it("is unsupported when push is not supported", async () => {
      webPush.isPushSupported.mockReturnValue(false);

      const { state } = await mountSettled();

      expect(state.value).toBe("unsupported");
    });

    it("does not touch Notification when push is unsupported", async () => {
      // On unsupported browsers (e.g. iOS Safari outside a PWA) the global
      // `Notification` may not exist at all; reading it would throw.
      webPush.isPushSupported.mockReturnValue(false);
      vi.unstubAllGlobals();

      const { state } = await mountSettled();

      expect(state.value).toBe("unsupported");
    });

    it("is ios-not-installed when supported but the iOS PWA is not installed", async () => {
      webPush.isIosNotInstalled.mockReturnValue(true);

      const { state } = await mountSettled();

      expect(state.value).toBe("ios-not-installed");
    });

    it("prefers unsupported over ios-not-installed", async () => {
      webPush.isPushSupported.mockReturnValue(false);
      webPush.isIosNotInstalled.mockReturnValue(true);

      const { state } = await mountSettled();

      expect(state.value).toBe("unsupported");
    });

    it("prefers ios-not-installed over a denied permission", async () => {
      webPush.isIosNotInstalled.mockReturnValue(true);
      stubNotification("denied");

      const { state } = await mountSettled();

      expect(state.value).toBe("ios-not-installed");
    });

    it("is denied when the user has blocked notifications", async () => {
      stubNotification("denied");

      const { state } = await mountSettled();

      expect(state.value).toBe("denied");
    });

    it("is off when permission has not been requested yet, without querying subscriptions", async () => {
      stubNotification("default");

      const { state } = await mountSettled();

      expect(state.value).toBe("off");
      expect(webPush.getWebPushSubscription).not.toHaveBeenCalled();
    });

    it("is on when permission is granted and a subscription exists", async () => {
      stubNotification("granted");
      webPush.getWebPushSubscription.mockResolvedValue({ endpoint: "https://push.example.com/x" });

      const { state } = await mountSettled();

      expect(state.value).toBe("on");
    });

    it("is off when permission is granted but there is no subscription (e.g. it expired)", async () => {
      stubNotification("granted");
      webPush.getWebPushSubscription.mockResolvedValue(null);

      const { state } = await mountSettled();

      expect(state.value).toBe("off");
    });
  });

  describe("enable()", () => {
    it.each([
      ["unsupported", () => webPush.isPushSupported.mockReturnValue(false)],
      ["ios-not-installed", () => webPush.isIosNotInstalled.mockReturnValue(true)],
    ] as const)("is a no-op when state is %s", async (expected, arrange) => {
      arrange();
      const notification = stubNotification("default");
      const { enable, state } = await mountSettled();

      await enable();

      expect(state.value).toBe(expected);
      expect(notification.requestPermission).not.toHaveBeenCalled();
      expect(api.getVapidPublicKey).not.toHaveBeenCalled();
      expect(api.subscribeToPush).not.toHaveBeenCalled();
    });

    it("reports requesting while the permission prompt is open", async () => {
      const notification = stubNotification("default");
      const prompt = deferred<NotificationPermission>();
      notification.requestPermission.mockReturnValue(prompt.promise);
      const { enable, state } = await mountSettled();

      const pending = enable();

      expect(state.value).toBe("requesting");

      notification.permission = "denied";
      prompt.resolve("denied");
      await pending;
    });

    it("subscribes the browser with the decoded VAPID key, registers it with the API, and reports on", async () => {
      stubNotification("default", "granted");
      const { enable, state } = await mountSettled();

      await enable();

      expect(api.getVapidPublicKey).toHaveBeenCalledOnce();
      expect(webPush.base64ToUint8Array).toHaveBeenCalledWith("vapid-public-key");
      expect(webPush.subscribeToWebPush).toHaveBeenCalledWith(APP_SERVER_KEY);
      expect(api.subscribeToPush).toHaveBeenCalledWith(BROWSER_SUBSCRIPTION);
      expect(state.value).toBe("on");
    });

    it("registers with the API only after the browser subscription exists", async () => {
      stubNotification("default", "granted");
      const order: string[] = [];
      webPush.subscribeToWebPush.mockImplementation(() => {
        order.push("browser");
        return Promise.resolve(BROWSER_SUBSCRIPTION);
      });
      api.subscribeToPush.mockImplementation(() => {
        order.push("api");
        return Promise.resolve();
      });
      const { enable } = await mountSettled();

      await enable();

      expect(order).toEqual(["browser", "api"]);
    });

    it("does not report on before the API registration has finished", async () => {
      stubNotification("default", "granted");
      const registration = deferred<void>();
      api.subscribeToPush.mockReturnValue(registration.promise);
      const { enable, state } = await mountSettled();

      const pending = enable();
      await flushPromises();
      expect(state.value).toBe("requesting");

      registration.resolve();
      await pending;
      expect(state.value).toBe("on");
    });

    it("stops at the permission prompt and reflects denied when the user refuses", async () => {
      stubNotification("default", "denied");
      const { enable, state } = await mountSettled();

      await enable();

      expect(state.value).toBe("denied");
      expect(api.getVapidPublicKey).not.toHaveBeenCalled();
      expect(webPush.subscribeToWebPush).not.toHaveBeenCalled();
      expect(api.subscribeToPush).not.toHaveBeenCalled();
    });

    it("returns to off when the user dismisses the prompt without choosing", async () => {
      stubNotification("default", "default");
      const { enable, state } = await mountSettled();

      await enable();

      expect(state.value).toBe("off");
      expect(api.subscribeToPush).not.toHaveBeenCalled();
    });

    it("can retry from denied (browser may have been re-allowed) and subscribes if granted", async () => {
      stubNotification("denied", "granted");
      const { enable, state } = await mountSettled();
      expect(state.value).toBe("denied");

      await enable();

      expect(api.subscribeToPush).toHaveBeenCalledWith(BROWSER_SUBSCRIPTION);
      expect(state.value).toBe("on");
    });

    describe("failures", () => {
      it("rolls back the browser subscription, reports off and rethrows when fetching the VAPID key fails", async () => {
        stubNotification("default", "granted");
        const error = new Error("vapid failed");
        api.getVapidPublicKey.mockRejectedValue(error);
        const { enable, state } = await mountSettled();

        await expect(enable()).rejects.toBe(error);

        expect(state.value).toBe("off");
        expect(webPush.subscribeToWebPush).not.toHaveBeenCalled();
        expect(webPush.unsubscribeFromWebPush).toHaveBeenCalledOnce();
      });

      it("rolls back and rethrows when the browser refuses to subscribe", async () => {
        stubNotification("default", "granted");
        const error = new Error("subscribe failed");
        webPush.subscribeToWebPush.mockRejectedValue(error);
        const { enable, state } = await mountSettled();

        await expect(enable()).rejects.toBe(error);

        expect(state.value).toBe("off");
        expect(api.subscribeToPush).not.toHaveBeenCalled();
        expect(webPush.unsubscribeFromWebPush).toHaveBeenCalledOnce();
      });

      it("removes the local subscription when the backend registration fails, so the browser and server don't drift apart", async () => {
        stubNotification("default", "granted");
        const error = new Error("backend 500");
        api.subscribeToPush.mockRejectedValue(error);
        const { enable, state } = await mountSettled();

        await expect(enable()).rejects.toBe(error);

        expect(webPush.unsubscribeFromWebPush).toHaveBeenCalledOnce();
        expect(state.value).toBe("off");
      });

      it("can be retried after a failure", async () => {
        stubNotification("default", "granted");
        api.subscribeToPush.mockRejectedValueOnce(new Error("backend 500"));
        const { enable, state } = await mountSettled();
        await expect(enable()).rejects.toThrow("backend 500");
        expect(state.value).toBe("off");

        await enable();

        expect(state.value).toBe("on");
        expect(api.subscribeToPush).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe("disable()", () => {
    async function mountEnabled() {
      stubNotification("granted");
      webPush.getWebPushSubscription.mockResolvedValue({
        endpoint: "https://push.example.com/existing",
      });
      const composable = await mountSettled();
      expect(composable.state.value).toBe("on");
      return composable;
    }

    it("removes the browser subscription, tells the API about that exact endpoint, and reports off", async () => {
      webPush.unsubscribeFromWebPush.mockResolvedValue("https://push.example.com/existing");
      const { disable, state } = await mountEnabled();

      await disable();

      expect(webPush.unsubscribeFromWebPush).toHaveBeenCalledOnce();
      expect(api.unsubscribeFromPush).toHaveBeenCalledWith("https://push.example.com/existing");
      expect(state.value).toBe("off");
    });

    it("does not call the API when there was no browser subscription to remove", async () => {
      // Nothing local means nothing to deregister; calling the API with an
      // empty endpoint would be a bad request at best.
      stubNotification("granted");
      webPush.getWebPushSubscription.mockResolvedValue(null);
      webPush.unsubscribeFromWebPush.mockResolvedValue(null);
      const { disable, state } = await mountSettled();

      await disable();

      expect(api.unsubscribeFromPush).not.toHaveBeenCalled();
      expect(state.value).toBe("off");
    });

    it("rethrows and re-syncs state with reality when the API call fails", async () => {
      const error = new Error("backend 500");
      api.unsubscribeFromPush.mockRejectedValue(error);
      const { disable, state } = await mountEnabled();
      // The browser subscription really was removed before the API call failed.
      webPush.getWebPushSubscription.mockResolvedValue(null);

      await expect(disable()).rejects.toBe(error);

      expect(state.value).toBe("off");
    });

    it("keeps reporting on when the browser unsubscribe fails and the subscription is still there", async () => {
      const error = new Error("unsubscribe failed");
      webPush.unsubscribeFromWebPush.mockRejectedValue(error);
      const { disable, state } = await mountEnabled();

      await expect(disable()).rejects.toBe(error);

      expect(api.unsubscribeFromPush).not.toHaveBeenCalled();
      expect(state.value).toBe("on");
    });
  });
});

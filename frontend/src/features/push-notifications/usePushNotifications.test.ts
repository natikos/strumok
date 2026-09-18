import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";

import { usePushNotifications } from "./usePushNotifications";

/**
 * `usePushNotifications` decides, from a handful of browser globals, whether a
 * resident can even be reminded (`unsupported`/`ios-not-installed`), whether
 * they've blocked it (`denied`), and whether a subscription already exists
 * (`on`/`off`). Each global is mocked individually here rather than assuming a
 * single "supported" bucket, because the composable branches on each one
 * independently and a bug in any single check (e.g. treating an installed iOS
 * PWA as "not installed") would otherwise go unnoticed.
 */

const { getVapidPublicKey, subscribeToPush, unsubscribeFromPush } = vi.hoisted(() => ({
  getVapidPublicKey: vi.fn(),
  subscribeToPush: vi.fn(),
  unsubscribeFromPush: vi.fn(),
}));

vi.mock("@shared/api/push", () => ({
  getVapidPublicKey,
  subscribeToPush,
  unsubscribeFromPush,
}));

const DESKTOP_CHROME_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
const IPHONE_SAFARI_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 " +
  "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";

interface Registration {
  pushManager: {
    getSubscription: ReturnType<typeof vi.fn>;
    subscribe: ReturnType<typeof vi.fn>;
  };
}

interface StubOptions {
  hasNotification?: boolean;
  hasPushManager?: boolean;
  hasServiceWorker?: boolean;
  matchesStandalone?: boolean;
  navigatorStandalone?: boolean;
  notificationPermission?: NotificationPermission;
  userAgent?: string;
}

function makeRegistration(): Registration {
  return {
    pushManager: {
      getSubscription: vi.fn().mockResolvedValue(null),
      subscribe: vi.fn(),
    },
  };
}

/** Installs the browser globals the composable reads, and returns handles to control them per test. */
function stubBrowserApis(options: StubOptions = {}) {
  const {
    hasNotification = true,
    hasPushManager = true,
    hasServiceWorker = true,
    matchesStandalone = false,
    navigatorStandalone = false,
    notificationPermission = "default",
    userAgent = DESKTOP_CHROME_UA,
  } = options;

  const requestPermission = vi.fn().mockResolvedValue(notificationPermission);
  if (hasNotification) {
    vi.stubGlobal("Notification", {
      permission: notificationPermission,
      requestPermission,
    });
  }

  if (hasPushManager) {
    vi.stubGlobal("PushManager", class {});
  }

  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      addEventListener: vi.fn(),
      matches: query === "(display-mode: standalone)" && matchesStandalone,
      removeEventListener: vi.fn(),
    }))
  );

  Object.defineProperty(navigator, "userAgent", { configurable: true, value: userAgent });
  Object.defineProperty(navigator, "standalone", {
    configurable: true,
    value: navigatorStandalone,
  });

  const registration = makeRegistration();
  if (hasServiceWorker) {
    // `"serviceWorker" in navigator` checks property *existence*, so the
    // "unsupported" case must leave the property entirely absent rather than
    // defined-with-undefined, or the composable would wrongly see it as present.
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { ready: Promise.resolve(registration) },
    });
  }

  return { registration, requestPermission };
}

function mountComposable() {
  let result!: ReturnType<typeof usePushNotifications>;
  const Harness = defineComponent({
    setup() {
      result = usePushNotifications();
      return () => h("div");
    },
  });
  mount(Harness);
  return {
    get result() {
      return result;
    },
  };
}

describe("usePushNotifications", () => {
  beforeEach(() => {
    getVapidPublicKey.mockReset();
    subscribeToPush.mockReset();
    unsubscribeFromPush.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete (navigator as { userAgent?: unknown }).userAgent;
    delete (navigator as { standalone?: unknown }).standalone;
    delete (navigator as { serviceWorker?: unknown }).serviceWorker;
  });

  describe("initial state", () => {
    it("is unsupported when the browser has no PushManager", async () => {
      stubBrowserApis({ hasPushManager: false });

      const { result } = mountComposable();
      await flushPromises();

      expect(result.state.value).toBe("unsupported");
    });

    it("is unsupported when the browser has no service worker support", async () => {
      stubBrowserApis({ hasServiceWorker: false });

      const { result } = mountComposable();
      await flushPromises();

      expect(result.state.value).toBe("unsupported");
    });

    it("is ios-not-installed for iPhone Safari not added to the home screen", async () => {
      stubBrowserApis({
        userAgent: IPHONE_SAFARI_UA,
        matchesStandalone: false,
        navigatorStandalone: false,
      });

      const { result } = mountComposable();
      await flushPromises();

      expect(result.state.value).toBe("ios-not-installed");
    });

    it("is not ios-not-installed once the iPhone PWA has been added to the home screen", async () => {
      // Installed via navigator.standalone (older iOS API).
      stubBrowserApis({
        userAgent: IPHONE_SAFARI_UA,
        navigatorStandalone: true,
        notificationPermission: "default",
      });

      const { result } = mountComposable();
      await flushPromises();

      expect(result.state.value).not.toBe("ios-not-installed");
    });

    it("is not ios-not-installed when installed detection comes from the display-mode media query", async () => {
      stubBrowserApis({
        userAgent: IPHONE_SAFARI_UA,
        matchesStandalone: true,
        notificationPermission: "default",
      });

      const { result } = mountComposable();
      await flushPromises();

      expect(result.state.value).not.toBe("ios-not-installed");
    });

    it("is denied when the user has blocked notifications", async () => {
      stubBrowserApis({ notificationPermission: "denied" });

      const { result } = mountComposable();
      await flushPromises();

      expect(result.state.value).toBe("denied");
    });

    it("is off when permission has not been requested yet", async () => {
      stubBrowserApis({ notificationPermission: "default" });

      const { result } = mountComposable();
      await flushPromises();

      expect(result.state.value).toBe("off");
    });

    it("is on when permission is granted and a push subscription already exists", async () => {
      const { registration } = stubBrowserApis({ notificationPermission: "granted" });
      registration.pushManager.getSubscription.mockResolvedValue({
        endpoint: "https://push.example.com/x",
      });

      const { result } = mountComposable();
      await flushPromises();

      expect(result.state.value).toBe("on");
    });

    it("is off when permission is granted but no push subscription exists", async () => {
      const { registration } = stubBrowserApis({ notificationPermission: "granted" });
      registration.pushManager.getSubscription.mockResolvedValue(null);

      const { result } = mountComposable();
      await flushPromises();

      expect(result.state.value).toBe("off");
    });
  });

  describe("enable()", () => {
    it("is a no-op when unsupported", async () => {
      stubBrowserApis({ hasPushManager: false });
      const { result } = mountComposable();
      await flushPromises();

      await result.enable();
      await flushPromises();

      expect(result.state.value).toBe("unsupported");
      expect(getVapidPublicKey).not.toHaveBeenCalled();
    });

    it("is a no-op when the iOS PWA is not installed", async () => {
      stubBrowserApis({ userAgent: IPHONE_SAFARI_UA });
      const { result } = mountComposable();
      await flushPromises();

      await result.enable();
      await flushPromises();

      expect(result.state.value).toBe("ios-not-installed");
      expect(getVapidPublicKey).not.toHaveBeenCalled();
    });

    it("flips to requesting immediately, then subscribes and reports the correct payload once permission is granted", async () => {
      const { registration, requestPermission } = stubBrowserApis({
        notificationPermission: "default",
      });
      requestPermission.mockResolvedValue("granted");
      getVapidPublicKey.mockResolvedValue("AAECAw"); // base64url(no padding) of bytes [0,1,2,3]
      const subscription = {
        toJSON: () => ({
          endpoint: "https://push.example.com/new",
          keys: { p256dh: "p-key", auth: "a-key" },
        }),
      };
      registration.pushManager.subscribe.mockResolvedValue(subscription);
      subscribeToPush.mockResolvedValue(undefined);

      const { result } = mountComposable();
      await flushPromises();

      const enabling = result.enable();
      expect(result.state.value).toBe("requesting");
      await enabling;

      expect(result.state.value).toBe("on");
      expect(registration.pushManager.subscribe).toHaveBeenCalledWith(
        expect.objectContaining({
          applicationServerKey: new Uint8Array([0, 1, 2, 3]),
          userVisibleOnly: true,
        })
      );
      expect(subscribeToPush).toHaveBeenCalledWith({
        endpoint: "https://push.example.com/new",
        keys: { p256dh: "p-key", auth: "a-key" },
      });
    });

    it("does not subscribe over the API and falls back to off when permission is refused", async () => {
      const { requestPermission } = stubBrowserApis({ notificationPermission: "default" });
      requestPermission.mockResolvedValue("denied");

      const { result } = mountComposable();
      await flushPromises();

      await result.enable();
      await flushPromises();

      expect(subscribeToPush).not.toHaveBeenCalled();
      expect(getVapidPublicKey).not.toHaveBeenCalled();
    });

    it("unsubscribes locally and reports off without calling the API when the browser subscription is incomplete", async () => {
      // A subscription missing its endpoint/keys can't be registered with the
      // backend; the composable must clean it up locally rather than send a
      // useless subscribe request.
      const { registration, requestPermission } = stubBrowserApis({
        notificationPermission: "default",
      });
      requestPermission.mockResolvedValue("granted");
      getVapidPublicKey.mockResolvedValue("AAECAw");
      const unsubscribe = vi.fn().mockResolvedValue(true);
      registration.pushManager.subscribe.mockResolvedValue({
        toJSON: () => ({ endpoint: "", keys: {} }),
        unsubscribe,
      });

      const { result } = mountComposable();
      await flushPromises();

      await result.enable();
      await flushPromises();

      expect(unsubscribe).toHaveBeenCalledOnce();
      expect(subscribeToPush).not.toHaveBeenCalled();
      expect(result.state.value).toBe("off");
    });
  });

  describe("disable()", () => {
    it("unsubscribes both the API and the browser subscription, then reports off", async () => {
      const { registration } = stubBrowserApis({ notificationPermission: "granted" });
      const unsubscribe = vi.fn().mockResolvedValue(true);
      registration.pushManager.getSubscription.mockResolvedValue({
        endpoint: "https://push.example.com/existing",
        unsubscribe,
      });
      unsubscribeFromPush.mockResolvedValue(undefined);

      const { result } = mountComposable();
      await flushPromises();
      expect(result.state.value).toBe("on");

      await result.disable();
      await flushPromises();

      expect(unsubscribeFromPush).toHaveBeenCalledWith("https://push.example.com/existing");
      expect(unsubscribe).toHaveBeenCalledOnce();
      expect(result.state.value).toBe("off");
    });

    it("does not call the API when there is no browser subscription to remove", async () => {
      const { registration } = stubBrowserApis({ notificationPermission: "granted" });
      registration.pushManager.getSubscription.mockResolvedValue(null);

      const { result } = mountComposable();
      await flushPromises();

      await result.disable();
      await flushPromises();

      expect(unsubscribeFromPush).not.toHaveBeenCalled();
      expect(result.state.value).toBe("off");
    });
  });
});

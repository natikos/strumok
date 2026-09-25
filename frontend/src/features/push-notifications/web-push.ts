import type { components } from "@/shared/api/generated/openapi";

type PushSubscriptionIn = components["schemas"]["PushSubscriptionIn"];

/**
 * Retrieves the current web push subscription if it exists and is valid.
 */
export async function getWebPushSubscription(): Promise<PushSubscriptionIn | null> {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  const serializedSubscription = subscription?.toJSON();

  if (
    !subscription ||
    !(
      serializedSubscription?.endpoint &&
      serializedSubscription?.keys?.["p256dh"] &&
      serializedSubscription?.keys?.["auth"]
    )
  ) {
    return null;
  }

  return {
    endpoint: serializedSubscription.endpoint,
    keys: {
      p256dh: serializedSubscription.keys["p256dh"],
      auth: serializedSubscription.keys["auth"],
    },
  };
}

export async function subscribeToWebPush(
  applicationServerKey: BufferSource
): Promise<PushSubscriptionIn> {
  const registration = await navigator.serviceWorker.ready;
  await registration.pushManager.subscribe({
    applicationServerKey,
    userVisibleOnly: true,
  });

  const subscription = await getWebPushSubscription();
  if (!subscription) {
    throw new Error("Push subscription succeeded but no subscription was found afterward");
  }
  return subscription;
}

export async function unsubscribeFromWebPush(): Promise<string> {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  await subscription?.unsubscribe();
  return subscription?.endpoint ?? "";
}

export function isPushSupported(): boolean {
  return "Notification" in window && "serviceWorker" in navigator && "PushManager" in window;
}

/**
 * Checks whether iOS is running the app outside the installed PWA.
 */
export function isIosNotInstalled(): boolean {
  const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone;
  return isIos && !isStandalone;
}

/**
 * Converts a URL-safe Base64 string to a Uint8Array.
 */
export function base64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const normalized = base64
    .replace(/-/g, "+")
    .replace(/_/g, "/")
    .padEnd(Math.ceil(base64.length / 4) * 4, "=");

  return Uint8Array.from(atob(normalized), (char) => char.charCodeAt(0));
}

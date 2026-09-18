import { computed, onMounted, ref } from "vue";

import { getVapidPublicKey, subscribeToPush, unsubscribeFromPush } from "@shared/api/push";

export type PushToggleState =
  | "denied"
  | "ios-not-installed"
  | "off"
  | "on"
  | "requesting"
  | "unsupported";

function isSupported(): boolean {
  return "Notification" in window && "serviceWorker" in navigator && "PushManager" in window;
}

function isIosNotInstalled(): boolean {
  const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return isIos && !isStandalone;
}

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const output = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    output[i] = rawData.charCodeAt(i);
  }
  return output;
}

export function usePushNotifications() {
  const state = ref<PushToggleState>("off");

  async function refreshState(): Promise<void> {
    if (!isSupported()) {
      state.value = "unsupported";
      return;
    }
    if (isIosNotInstalled()) {
      state.value = "ios-not-installed";
      return;
    }
    if (Notification.permission === "denied") {
      state.value = "denied";
      return;
    }
    if (Notification.permission === "granted") {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      state.value = subscription ? "on" : "off";
      return;
    }
    state.value = "off";
  }

  onMounted(() => {
    void refreshState();
  });

  async function enable(): Promise<void> {
    if (state.value === "unsupported" || state.value === "ios-not-installed") {
      return;
    }

    state.value = "requesting";
    let subscription: PushSubscription | undefined;
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        await refreshState();
        return;
      }

      const registration = await navigator.serviceWorker.ready;
      const publicKey = await getVapidPublicKey();
      subscription = await registration.pushManager.subscribe({
        applicationServerKey: urlBase64ToUint8Array(publicKey),
        userVisibleOnly: true,
      });

      const json = subscription.toJSON();
      const p256dh = json.keys?.["p256dh"];
      const auth = json.keys?.["auth"];
      if (!json.endpoint || !p256dh || !auth) {
        await subscription.unsubscribe();
        state.value = "off";
        return;
      }

      await subscribeToPush({ endpoint: json.endpoint, keys: { p256dh, auth } });
      state.value = "on";
    } catch (error) {
      // The browser-level subscription may have succeeded even if telling the
      // server about it failed; without this the UI would be stuck on
      // "requesting" for a subscription the server never received.
      await subscription?.unsubscribe();
      state.value = "off";
      throw error;
    }
  }

  async function disable(): Promise<void> {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await unsubscribeFromPush(subscription.endpoint);
        await subscription.unsubscribe();
      }
      state.value = "off";
    } catch (error) {
      await refreshState();
      throw error;
    }
  }

  return {
    state: computed(() => state.value),
    enable,
    disable,
  };
}

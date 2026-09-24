import { computed, onMounted, ref } from "vue";

import { getVapidPublicKey, subscribeToPush, unsubscribeFromPush } from "@/shared/api/push";

import {
  base64ToUint8Array,
  getWebPushSubscription,
  isIosNotInstalled,
  isPushSupported,
  subscribeToWebPush,
  unsubscribeFromWebPush,
} from "./web-push";

export type PushToggleState =
  | "denied"
  | "ios-not-installed"
  | "off"
  | "on"
  | "requesting"
  | "unsupported";

export function usePushNotifications() {
  const state = ref<PushToggleState>("off");

  async function refreshState(): Promise<void> {
    if (!isPushSupported()) {
      state.value = "unsupported";
      return;
    }

    if (isIosNotInstalled()) {
      state.value = "ios-not-installed";
      return;
    }

    switch (Notification.permission) {
      case "denied":
        state.value = "denied";
        break;

      case "granted":
        state.value = (await getWebPushSubscription()) ? "on" : "off";
        break;

      default:
        state.value = "off";
    }
  }

  onMounted(() => {
    void refreshState();
  });

  async function enable(): Promise<void> {
    if (state.value === "unsupported" || state.value === "ios-not-installed") {
      return;
    }

    state.value = "requesting";

    try {
      const permission = await Notification.requestPermission();

      if (permission !== "granted") {
        await refreshState();
        return;
      }

      const appServerKey = base64ToUint8Array(await getVapidPublicKey());
      const subscription = await subscribeToWebPush(appServerKey);
      await subscribeToPush(subscription);
      state.value = "on";
    } catch (error) {
      await unsubscribeFromWebPush();
      state.value = "off";
      throw error;
    }
  }

  async function disable(): Promise<void> {
    try {
      const endpoint = await unsubscribeFromWebPush();
      await unsubscribeFromPush(endpoint);
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

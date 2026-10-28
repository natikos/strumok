import { onBeforeUnmount, readonly, ref } from "vue";

/** Reactive `navigator.onLine`, kept current by the browser's online/offline events. */
export function useOnlineStatus() {
  const isOnline = ref(typeof navigator === "undefined" ? true : navigator.onLine);

  const setOnline = () => {
    isOnline.value = true;
  };
  const setOffline = () => {
    isOnline.value = false;
  };

  if (typeof window !== "undefined") {
    window.addEventListener("online", setOnline);
    window.addEventListener("offline", setOffline);
    onBeforeUnmount(() => {
      window.removeEventListener("online", setOnline);
      window.removeEventListener("offline", setOffline);
    });
  }

  return { isOnline: readonly(isOnline), setOnline };
}

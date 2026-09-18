/// <reference lib="webworker" />
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

self.skipWaiting();
cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// SPA fallback: serve index.html for navigations, except API/docs/static asset paths.
const NAVIGATE_FALLBACK_DENYLIST = [
  /^\/favicon\//,
  /^\/(?:health|docs|redoc|openapi\.json)(?:\/|$)/,
  /\.(?:png|jpe?g|gif|svg|ico|webp|woff2?|ttf|otf|eot|webmanifest|json)$/,
];
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("index.html"), {
    denylist: NAVIGATE_FALLBACK_DENYLIST,
  })
);

interface PushNotificationPayload {
  title: string;
  body: string;
  url: string;
}

const DEFAULT_PUSH_PAYLOAD: PushNotificationPayload = { title: "Strumok", body: "", url: "/" };

function parsePushPayload(event: PushEvent): PushNotificationPayload {
  if (!event.data) {
    return DEFAULT_PUSH_PAYLOAD;
  }
  try {
    const data = event.data.json();
    return {
      title:
        typeof data?.title === "string" && data.title ? data.title : DEFAULT_PUSH_PAYLOAD.title,
      body: typeof data?.body === "string" ? data.body : DEFAULT_PUSH_PAYLOAD.body,
      url: typeof data?.url === "string" && data.url ? data.url : DEFAULT_PUSH_PAYLOAD.url,
    };
  } catch {
    // Malformed/non-JSON payload: still show a notification rather than let the handler throw.
    return DEFAULT_PUSH_PAYLOAD;
  }
}

self.addEventListener("push", (event: PushEvent) => {
  const payload = parsePushPayload(event);

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/favicon/web-app-manifest-192x192.png",
      data: { url: payload.url },
    })
  );
});

self.addEventListener("notificationclick", (event: NotificationEvent) => {
  event.notification.close();
  const targetUrl: string = event.notification.data?.url ?? "/";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      const existing = clients.find((client) => "focus" in client);
      if (existing) {
        const existingUrl = new URL(existing.url).pathname;
        return existing
          .focus()
          .then(() => (existingUrl === targetUrl ? existing : existing.navigate(targetUrl)));
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});

// Browsers may rotate/expire a subscription outside of the app's control; re-subscribe
// and push the new endpoint to the server so reminders don't silently stop working.
interface PushSubscriptionChangeEvent extends ExtendableEvent {
  oldSubscription: PushSubscription | null;
  newSubscription: PushSubscription | null;
}

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = self.atob(base64);
  const output = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    output[i] = rawData.charCodeAt(i);
  }
  return output;
}

async function resyncPushSubscription(event: PushSubscriptionChangeEvent): Promise<void> {
  const oldEndpoint = event.oldSubscription?.endpoint;

  const subscription =
    event.newSubscription ??
    (await self.registration.pushManager.subscribe({
      applicationServerKey: urlBase64ToUint8Array(
        await fetch(`${API_BASE_URL}/push/vapid-public-key`, { credentials: "include" })
          .then((res) => res.json())
          .then((body) => body.public_key)
      ),
      userVisibleOnly: true,
    }));

  const json = subscription.toJSON();
  if (!json.endpoint || !json.keys?.["p256dh"] || !json.keys?.["auth"]) {
    return;
  }

  await fetch(`${API_BASE_URL}/push/subscribe`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: json.endpoint,
      keys: { p256dh: json.keys["p256dh"], auth: json.keys["auth"] },
    }),
  });

  if (oldEndpoint && oldEndpoint !== json.endpoint) {
    await fetch(`${API_BASE_URL}/push/subscribe`, {
      method: "DELETE",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: oldEndpoint }),
    });
  }
}

self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(resyncPushSubscription(event as PushSubscriptionChangeEvent));
});

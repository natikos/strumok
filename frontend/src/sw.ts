import { clientsClaim } from "workbox-core";
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";

import { navigationDenylist } from "@/shared/pwa/navigationDenylist";

declare let self: ServiceWorkerGlobalScope;

self.skipWaiting();
clientsClaim();

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// Deep links such as /history are client routes with no file behind them, so a
// navigation falls back to the precached shell; backend paths and files must
// still reach the network.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("/index.html"), {
    denylist: navigationDenylist,
  })
);

self.addEventListener("push", (event) => {
  if (!event.data) {
    return;
  }

  const data = event.data.json();

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/favicon/web-app-manifest-192x192.png",
      badge: "/favicon/web-app-manifest-192x192.png",
      data: {
        url: data.url,
      },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const url = event.notification.data?.url;

  if (!url) {
    return;
  }

  event.waitUntil(self.clients.openWindow(url));
});

/*
 * Push notification handlers for ExSize (issue #65, faza 6).
 *
 * Loaded by the Workbox-generated service worker via `workbox.importScripts`
 * (see src/pwa-config.ts). This lets us handle `push` / `notificationclick`
 * without switching the PWA from generateSW to injectManifest — the existing
 * precaching and runtime caching (and their tests) stay untouched.
 *
 * Plain JS on purpose: importScripts loads it as-is in the SW scope.
 */

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_err) {
    // Payload nie jest JSON-em — pokaż surowy tekst lub fallback.
    payload = { title: "ExSize", body: event.data ? event.data.text() : "" };
  }

  const title = payload.title || "ExSize";
  const body =
    payload.body ||
    (Array.isArray(payload.titles) && payload.titles.length
      ? payload.titles.join(", ")
      : "Masz nowe przypomnienie");

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/pwa-192x192.png",
      badge: "/pwa-192x192.png",
      tag: "exsize-reminder",
      renotify: true,
      data: { url: payload.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl =
    (event.notification.data && event.notification.data.url) || "/";

  event.waitUntil(
    (async () => {
      const clientList = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      for (const client of clientList) {
        if ("focus" in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })()
  );
});

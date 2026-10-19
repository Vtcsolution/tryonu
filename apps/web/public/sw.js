/* TryOnU service worker: makes the site installable and shows phone
   notifications. It does not cache pages, so the site is never stale. */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "TryOnU";
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(title, {
        body: data.body || "Something new on TryOnU",
        icon: "/pwa/icon-192.png",
        badge: "/pwa/badge-96.png",
        tag: data.tag,
        data: { url: data.url || "/notifications" },
      }),
      // an open TryOnU tab refreshes its bell
      self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((tabs) =>
        tabs.forEach((tab) => tab.postMessage({ type: "tryonu-notification" })),
      ),
    ]),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL((event.notification.data && event.notification.data.url) || "/notifications", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((tabs) => {
      const open = tabs.find((tab) => tab.url.startsWith(self.location.origin));
      if (open) return open.focus().then(() => open.navigate(url));
      return self.clients.openWindow(url);
    }),
  );
});

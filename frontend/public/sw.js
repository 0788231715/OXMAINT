const CACHE_PREFIX = "oxmaint-app-shell-";
const CACHE_NAME = `${CACHE_PREFIX}v1`;

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const shellResponse = await fetch("/", { cache: "reload" });
    if (!shellResponse.ok) {
      throw new Error(`Could not cache the application shell (${shellResponse.status}).`);
    }
    const html = await shellResponse.clone().text();
    const assets = [...html.matchAll(/(?:src|href)=["']([^"']+\.(?:js|css)(?:\?[^"']*)?)["']/g)]
      .map(match => new URL(match[1], self.location.origin).href)
      .filter(url => new URL(url).origin === self.location.origin);
    const cache = await caches.open(CACHE_NAME);
    await cache.put("/", shellResponse);
    await cache.addAll([
      "/manifest.webmanifest",
      "/oxmaint-icon.svg",
      ...new Set(assets.map(url => new URL(url).pathname)),
    ]);
  })());
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter(name => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
        .map(name => caches.delete(name))
    );
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (response.ok) {
          const cache = await caches.open(CACHE_NAME);
          await cache.put("/", response.clone());
        }
        return response;
      } catch {
        const cached = await caches.match("/");
        if (cached) return cached;
        throw new Error("The OxMaint application shell is not cached for offline use.");
      }
    })());
    return;
  }

  event.respondWith((async () => {
    const cached = await caches.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      await cache.put(request, response.clone());
    }
    return response;
  })());
});

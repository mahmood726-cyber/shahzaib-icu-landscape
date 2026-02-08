/* ─────────────────────────────────────────────────────────────────────────────
 * sw.js — Service Worker for ICU Living Evidence Map (offline support)
 *
 * Strategy: Network-first for data files, cache-first for static assets.
 * ────────────────────────────────────────────────────────────────────────── */

const CACHE_VERSION = 2;
const CACHE_NAME = `icu-evidence-map-v${CACHE_VERSION}`;

const STATIC_ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./plotly_charts.js",
  "./data-worker.js",
  "./lib/plotly.min.js",
];

const DATA_PATTERNS = [
  /\/data\//,
];

// Install: cache static assets (individual puts so one failure doesn't block all)
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.allSettled(
        STATIC_ASSETS.map((asset) =>
          cache.add(asset).catch((err) => {
            console.warn(`SW: failed to cache ${asset}:`, err.message);
          })
        )
      )
    )
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Fetch: network-first for data, cache-first for static
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Only handle same-origin GET requests
  if (event.request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  const isData = DATA_PATTERNS.some((pattern) => pattern.test(url.pathname));

  if (isData) {
    // Network-first for data files (always want fresh data)
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
  } else {
    // Cache-first for static assets
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
  }
});

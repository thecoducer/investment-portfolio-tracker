// Metron Service Worker — cache-first for static assets, network-first for API
const CACHE_NAME = 'metron-v1';
const STATIC_ASSETS = [
  '/',
  '/static/css/styles.css',
  '/static/css/landing.css',
  '/static/css/public-pages.css',
  '/static/images/favicon.svg',
  '/static/images/icon-192x192.png',
  '/static/images/icon-512x512.png',
  '/static/images/metron-logo-light.svg',
  '/static/images/metron-logo-dark.svg',
  '/static/manifest.json'
];

// Install — pre-cache essential static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate — clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch — static assets: cache-first; API/pages: network-first
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // API requests — always network, no caching
  if (url.pathname.startsWith('/api/')) return;

  // Static assets — cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(cached =>
        cached || fetch(event.request).then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return response;
        })
      )
    );
    return;
  }

  // Pages — network-first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then(response => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

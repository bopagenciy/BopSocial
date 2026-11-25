/* Bop Social Service Worker — caches app shell for offline + Add to Home Screen */
const CACHE_NAME = 'bopsocial-__BUILD_ID__';
const SHELL_ASSETS = ['/', '/index.html'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  // Only handle same-origin GET requests
  if (request.method !== 'GET') return;
  // Never cache authenticated requests, API calls, or private media
  if (request.headers && request.headers.get('Authorization')) return;
  if (request.url.includes('/api/') || request.url.includes('/media/')) return;
  // Never cache hashed JS/CSS chunks in SW so new deployments never reuse old chunks
  if (request.url.includes('/static/js/') || request.url.includes('/static/css/')) return;

  // For HTML navigation requests, use Network-First strategy to ensure fresh releases are served
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match('/index.html')))
    );
    return;
  }

  // For non-hashed static brand assets (icons, images, fonts), use Network-First with cache fallback
  if (request.url.match(/\.(png|jpg|jpeg|svg|webp|woff2?)$/)) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
  }
});

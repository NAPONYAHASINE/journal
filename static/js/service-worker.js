// --- Service Worker PWA avancé ---
const CACHE_NAME = 'ngabloomhub-cache-v2';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/manifest.json',
  // Ajoute ici d'autres fichiers statiques à mettre en cache initialement
];

// Installation : cache initial
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
  self.skipWaiting();
});

// Activation : nettoyage des anciens caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames =>
      Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

// Fetch : cache dynamique
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      if (response) return response;
      return fetch(event.request).then(fetchResponse => {
        // Cache dynamiquement les nouvelles ressources GET
        if (event.request.method === 'GET' && fetchResponse && fetchResponse.status === 200 && fetchResponse.type === 'basic') {
          const responseToCache = fetchResponse.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
        }
        return fetchResponse;
      }).catch(() => {
        // Optionnel : retourne une page offline personnalisée
        // return caches.match('/offline.html');
      });
    })
  );
});

// Notifications push (désactivées temporairement)
// self.addEventListener('push', function(event) {
//   const data = event.data ? event.data.json() : {};
//   const title = data.title || 'Notification';
//   const options = {
//     body: data.body || '',
//     icon: '/static/css/icon-192.png',
//     badge: '/static/css/icon-192.png',
//     data: data.url || '/'
//   };
//   event.waitUntil(self.registration.showNotification(title, options));
// });

// self.addEventListener('notificationclick', function(event) {
//   event.notification.close();
//   event.waitUntil(
//     clients.openWindow(event.notification.data)
//   );
// });

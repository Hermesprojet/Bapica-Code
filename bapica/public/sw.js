// Service Worker pour Bapica PWA
// Offline support + cache stratégies

const CACHE_NAME = 'bapica-v1'

// Pages à mettre en cache pour le mode offline
const PRECACHE_URLS = [
  '/',
  '/login',
  '/signup',
  '/manifest.json',
  '/favicon.ico',
  '/favicon.svg',
  '/icon-192.png',
  '/icon-512.png',
]

// Install: precache les assets essentiels
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS)
    })
  )
  // Activer immédiatement (ne pas attendre que les anciens onglets se ferment)
  self.skipWaiting()
})

// Activate: nettoyer les anciens caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))
      )
    })
  )
  // Prendre le contrôle de tous les clients immédiatement
  self.clients.claim()
})

// Fetch: stratégie Network First avec fallback cache
self.addEventListener('fetch', (event) => {
  // Ignorer les requêtes non-GET et les API
  if (event.request.method !== 'GET') return
  if (event.request.url.includes('/api/')) return
  if (event.request.url.includes('chrome-extension://')) return

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Mettre en cache les réponses réussies
        if (response.status === 200) {
          const responseClone = response.clone()
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone)
          })
        }
        return response
      })
      .catch(() => {
        // Offline: servir depuis le cache
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) return cachedResponse
          // Page offline par défaut
          if (event.request.mode === 'navigate') {
            return caches.match('/')
          }
          return new Response('', { status: 408 })
        })
      })
  )
})

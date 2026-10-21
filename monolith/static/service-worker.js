// AI Nurse Health Kiosk - Service Worker
// Version 1.0.0

const CACHE_NAME = 'ai-nurse-v1.0.0';
const RUNTIME_CACHE = 'ai-nurse-runtime-v1.0.0';

// Files to cache for offline support
const STATIC_CACHE_URLS = [
    '/',
    '/dashboard',
    '/patients',
    '/qr-scanner',
    '/static/manifest.json',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://code.jquery.com/jquery-3.7.1.min.js'
];

// Install event - cache static resources
self.addEventListener('install', (event) => {
    console.log('[Service Worker] Installing...');

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[Service Worker] Caching static assets');
                return cache.addAll(STATIC_CACHE_URLS.map(url => new Request(url, {
                    cache: 'reload'
                })));
            })
            .catch((error) => {
                console.error('[Service Worker] Cache failed:', error);
            })
    );

    // Force the waiting service worker to become the active service worker
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[Service Worker] Activating...');

    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE) {
                        console.log('[Service Worker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );

    // Take control of all pages immediately
    return self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip cross-origin requests (except CDN resources)
    if (url.origin !== location.origin && !request.url.includes('cdn.jsdelivr.net') && !request.url.includes('code.jquery.com')) {
        return;
    }

    // API requests - network first, cache fallback
    if (request.url.includes('/api/')) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    // Clone the response before caching
                    const responseClone = response.clone();

                    // Cache successful API responses
                    if (response.status === 200 || response.status === 201) {
                        caches.open(RUNTIME_CACHE).then((cache) => {
                            cache.put(request, responseClone);
                        });
                    }

                    return response;
                })
                .catch(() => {
                    // If network fails, try cache
                    return caches.match(request).then((cachedResponse) => {
                        if (cachedResponse) {
                            console.log('[Service Worker] Serving API from cache:', request.url);
                            return cachedResponse;
                        }

                        // Return offline response
                        return new Response(
                            JSON.stringify({
                                error: 'Network unavailable',
                                offline: true
                            }),
                            {
                                headers: { 'Content-Type': 'application/json' },
                                status: 503
                            }
                        );
                    });
                })
        );
        return;
    }

    // Static assets - cache first, network fallback
    event.respondWith(
        caches.match(request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    console.log('[Service Worker] Serving from cache:', request.url);
                    return cachedResponse;
                }

                // Not in cache, fetch from network
                return fetch(request)
                    .then((response) => {
                        // Don't cache if not a success response
                        if (!response || response.status !== 200 || response.type === 'error') {
                            return response;
                        }

                        // Clone the response
                        const responseClone = response.clone();

                        // Cache the fetched resource
                        caches.open(RUNTIME_CACHE).then((cache) => {
                            cache.put(request, responseClone);
                        });

                        return response;
                    })
                    .catch((error) => {
                        console.error('[Service Worker] Fetch failed:', error);

                        // Return offline page for navigation requests
                        if (request.mode === 'navigate') {
                            return caches.match('/').then((response) => {
                                return response || new Response(
                                    '<html><body><h1>Offline</h1><p>You are currently offline. Please check your internet connection.</p></body></html>',
                                    {
                                        headers: { 'Content-Type': 'text/html' }
                                    }
                                );
                            });
                        }

                        return new Response('Network error', {
                            status: 408,
                            headers: { 'Content-Type': 'text/plain' }
                        });
                    });
            })
    );
});

// Background sync event (for future use)
self.addEventListener('sync', (event) => {
    console.log('[Service Worker] Background sync:', event.tag);

    if (event.tag === 'sync-measurements') {
        event.waitUntil(syncMeasurements());
    }
});

// Push notification event (for future use)
self.addEventListener('push', (event) => {
    console.log('[Service Worker] Push notification received');

    const options = {
        body: event.data ? event.data.text() : 'New notification',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/icon-72x72.png',
        vibrate: [200, 100, 200],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            {
                action: 'explore',
                title: 'Open App'
            },
            {
                action: 'close',
                title: 'Close'
            }
        ]
    };

    event.waitUntil(
        self.registration.showNotification('AI Nurse', options)
    );
});

// Notification click event
self.addEventListener('notificationclick', (event) => {
    console.log('[Service Worker] Notification clicked:', event.action);

    event.notification.close();

    if (event.action === 'explore') {
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

// Message event - communicate with client
self.addEventListener('message', (event) => {
    console.log('[Service Worker] Message received:', event.data);

    if (event.data.action === 'skipWaiting') {
        self.skipWaiting();
    }

    if (event.data.action === 'clearCache') {
        event.waitUntil(
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => caches.delete(cacheName))
                );
            }).then(() => {
                event.ports[0].postMessage({ success: true });
            })
        );
    }

    if (event.data.action === 'cacheSize') {
        event.waitUntil(
            caches.keys().then(async (cacheNames) => {
                let totalSize = 0;

                for (const cacheName of cacheNames) {
                    const cache = await caches.open(cacheName);
                    const keys = await cache.keys();

                    for (const request of keys) {
                        const response = await cache.match(request);
                        const blob = await response.blob();
                        totalSize += blob.size;
                    }
                }

                event.ports[0].postMessage({
                    size: totalSize,
                    sizeFormatted: formatBytes(totalSize)
                });
            })
        );
    }
});

// Helper function - sync measurements (for future use)
async function syncMeasurements() {
    try {
        // Get pending measurements from IndexedDB
        // Send to server
        console.log('[Service Worker] Syncing measurements...');
        return Promise.resolve();
    } catch (error) {
        console.error('[Service Worker] Sync failed:', error);
        return Promise.reject(error);
    }
}

// Helper function - format bytes
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Log service worker status
console.log('[Service Worker] Loaded successfully');

// Offline-Cache für die App-Oberfläche. Anfragen an OpenAI werden nie zwischengespeichert.
const CACHE = 'uebersetzer-v5';
const SHELL = [
  './',
  'index.html',
  'style.css',
  'app.js',
  'talk.js',
  'manifest.json',
  'icons/icon.svg',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/apple-touch-icon.png',
  'icons/logo-rosanke.png',
  'fonts/montserrat-latin-600-normal.woff2',
  'fonts/montserrat-latin-700-normal.woff2',
  'fonts/open-sans-latin-400-normal.woff2',
  'fonts/open-sans-latin-600-normal.woff2',
  'fonts/open-sans-greek-400-normal.woff2',
  'fonts/open-sans-greek-600-normal.woff2',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// Netzwerk zuerst (damit Updates sofort ankommen), Cache als Rückfall ohne Netz.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      })
      .catch(() => caches.match(req).then((r) => r || caches.match('./'))),
  );
});

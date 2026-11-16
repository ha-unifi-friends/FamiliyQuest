// Family Quest service worker: keeps the app shell available (network first, cache as fallback).
// The API is never cached – learning state always comes from the app.
const CACHE = "fq-__VERSION__";
const SHELL = ["./", "kid.js", "kid.css", "shared/base.css", "shared/ui.js", "shared/i18n.js", "shared/avatar.js", "img/icon.svg", "manifest.webmanifest"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).catch(() => {})); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.includes("/api/")) return;
  e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {}); return r; })
    .catch(() => caches.match(e.request, { ignoreSearch: true })));
});

/* Service worker de AgroGestión — estrategia RED PRIMERO:
   - Con internet: siempre baja la versión más nueva (los deploys de Vercel
     llegan de inmediato, nunca se sirve una app vieja).
   - Sin internet (en el campo): sirve lo último que se cargó desde el caché.
   - Nunca toca peticiones a Supabase ni a otros dominios. */
const CACHE = "agrogestion-v1";

self.addEventListener("install", () => { self.skipWaiting(); });

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // Supabase y terceros: directo a la red

  e.respondWith(
    fetch(req)
      .then(res => {
        if (res && res.ok) {
          const copia = res.clone();
          caches.open(CACHE).then(c => c.put(req, copia));
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then(r =>
          r || (req.mode === "navigate" ? caches.match("/index.html") : Response.error())
        )
      )
  );
});

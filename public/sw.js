// ============================================================
//  AgroGestión — Service Worker (soporte offline)
//
//  Estrategia:
//  · App (HTML/JS/CSS propios): red primero → si no hay señal,
//    se sirve la copia guardada. Así siempre abres la app en
//    el campo, aunque no haya internet.
//  · Fuentes y librerías externas (Google Fonts, Leaflet):
//    caché primero — se descargan una vez y quedan guardadas.
//  · Los ICONOS no necesitan red nunca: van dibujados dentro
//    del propio código de la app (SVG).
// ============================================================
const CACHE_APP = "agrogestion-v2";
const CACHE_EXT = "agrogestion-ext-v2";
const PRECACHE = ["/", "/index.html", "/manifest.json", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_APP).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_APP && k !== CACHE_EXT).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  // Nunca interceptar Supabase (datos vivos; la app ya tiene su propia cola offline)
  if (url.hostname.endsWith("supabase.co")) return;

  // Externos (fuentes, leaflet): caché primero, luego red
  const esExterno = url.origin !== self.location.origin;
  if (esExterno) {
    e.respondWith(
      caches.open(CACHE_EXT).then(async (c) => {
        const hit = await c.match(request);
        if (hit) return hit;
        try {
          const resp = await fetch(request);
          if (resp && (resp.ok || resp.type === "opaque")) c.put(request, resp.clone());
          return resp;
        } catch {
          return hit || Response.error();
        }
      })
    );
    return;
  }

  // Navegación (abrir la app): red primero, caer al index guardado
  if (request.mode === "navigate") {
    e.respondWith(
      fetch(request)
        .then((resp) => {
          const copia = resp.clone();
          caches.open(CACHE_APP).then((c) => c.put("/index.html", copia));
          return resp;
        })
        .catch(() => caches.match("/index.html").then((r) => r || caches.match("/")))
    );
    return;
  }

  // Assets propios (JS/CSS/imagenes del build): red primero con respaldo en caché
  e.respondWith(
    fetch(request)
      .then((resp) => {
        if (resp && resp.ok) {
          const copia = resp.clone();
          caches.open(CACHE_APP).then((c) => c.put(request, copia));
        }
        return resp;
      })
      .catch(() => caches.match(request))
  );
});

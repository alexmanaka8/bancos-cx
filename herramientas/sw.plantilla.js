// Service worker: guarda la app en el celular para usarla sin internet.
// Lo genera herramientas/construir.py a partir de sw.plantilla.js: no lo edites a mano.
const VERSION = '__VERSION__';
const CACHE = 'bancos-' + VERSION;
const BIBLIOTECA = 'bancos-biblioteca';  // páginas de la biblioteca: se guardan al abrirlas
const ARCHIVOS = __ARCHIVOS__;

self.addEventListener('install', e => {
  // cache 'reload': descargar siempre la versión nueva, nunca una copia vieja guardada por el navegador
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ARCHIVOS.map(u => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== CACHE && k !== BIBLIOTECA).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  e.respondWith((async () => {
    // banco.html?id=x y banco.html son el mismo archivo guardado
    const guardado = await caches.match(req, { ignoreSearch: true });
    if (guardado) return guardado;
    try {
      const res = await fetch(req);
      if (res.ok && url.pathname.includes('/biblioteca/')) {
        (await caches.open(BIBLIOTECA)).put(req, res.clone());
      }
      return res;
    } catch (err) {
      if (req.mode === 'navigate') return caches.match('./index.html');
      throw err;
    }
  })());
});

self.addEventListener('message', e => {
  if (e.data === 'version') e.source.postMessage({ version: VERSION });
});

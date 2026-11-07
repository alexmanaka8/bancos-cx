// Service worker: guarda la app en el celular para usarla sin internet.
// Lo genera herramientas/construir.py a partir de sw.plantilla.js: no lo edites a mano.
const VERSION = 'fc50505063';
const CACHE = 'bancos-' + VERSION;
const BIBLIOTECA = 'bancos-biblioteca';  // páginas de la biblioteca: se guardan al abrirlas
const ARCHIVOS = [
 "./",
 "banco.html",
 "bancos/semana1/index.html",
 "biblioteca.html",
 "comun/app.css",
 "comun/app.js",
 "comun/integrar.css",
 "comun/integrar.js",
 "datos/banco-traducido.json",
 "datos/catalogo.json",
 "datos/cicatrizacion.json",
 "datos/examenes-2026.json",
 "datos/final-2021.json",
 "datos/fotos.json",
 "datos/lozano.json",
 "datos/pretest-2024.json",
 "datos/recopilacion-2021.json",
 "datos/simulacros.json",
 "fuentes/fuentes.css",
 "fuentes/ibm-plex-sans-effb1ea2.woff2",
 "fuentes/ibm-plex-sans-f6667783.woff2",
 "fuentes/jetbrains-mono-0137caee.woff2",
 "fuentes/jetbrains-mono-ee0ad6e8.woff2",
 "fuentes/newsreader-07e34f9e.woff2",
 "fuentes/newsreader-4aa9bb70.woff2",
 "fuentes/newsreader-4f36c1be.woff2",
 "fuentes/newsreader-997f7492.woff2",
 "iconos/apple-touch-icon.png",
 "iconos/favicon-64.png",
 "iconos/icono-192.png",
 "iconos/icono-512.png",
 "iconos/icono-maskable-512.png",
 "index.html",
 "manifest.webmanifest"
];

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

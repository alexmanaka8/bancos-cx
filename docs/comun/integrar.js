// Se agrega al final de cada banco HTML original: activa el modo sin internet.
(function () {
  var t = document.getElementById('pwa-titulo');
  if (t) t.textContent = document.title;
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('../../sw.js').catch(function () {});
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () {});
})();

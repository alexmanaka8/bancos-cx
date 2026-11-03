// Funciones comunes: guardar el progreso en el celular y activar el modo sin internet.
const App = (() => {
  const PREF = 'pwa:';

  // ---------- progreso (localStorage = memoria del navegador en este celular) ----------
  function vacio() { return { hist: {}, ses: null, clave: {}, flag: {} }; }
  function cargar(id) {
    try { const d = JSON.parse(localStorage.getItem(PREF + id)); if (d && d.hist) return Object.assign(vacio(), d); } catch (e) {}
    return vacio();
  }
  function guardar(id, d) {
    try { localStorage.setItem(PREF + id, JSON.stringify(d)); } catch (e) { aviso('No se pudo guardar el progreso (memoria llena).'); }
  }
  // Los bancos HTML originales guardan su progreso con su propia clave (formato {hist, ses}).
  function cargarHtml(clave) {
    try { const d = JSON.parse(localStorage.getItem(clave)); if (d && d.hist) return d; } catch (e) {}
    return { hist: {} };
  }
  function resumen(hist, total) {
    const v = Object.values(hist);
    const vistas = v.length;
    const bien = v.filter(h => h.last === true).length;
    const mal = v.filter(h => h.last === false).length;
    return { total, vistas, bien, mal, pct: bien + mal ? Math.round(bien / (bien + mal) * 100) : null };
  }

  // Copia de seguridad: todo lo guardado en un archivo .json
  function exportar() {
    const datos = {};
    for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); datos[k] = localStorage.getItem(k); }
    const blob = new Blob([JSON.stringify({ app: 'bancos-cx', fecha: new Date().toISOString(), datos })], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'progreso-bancos-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(a); a.click(); a.remove();
  }
  function importar(archivo, listo) {
    const r = new FileReader();
    r.onload = () => {
      try {
        const d = JSON.parse(r.result);
        if (d.app !== 'bancos-cx') throw new Error('archivo');
        Object.entries(d.datos).forEach(([k, v]) => localStorage.setItem(k, v));
        listo(true);
      } catch (e) { listo(false); }
    };
    r.readAsText(archivo);
  }

  // ---------- utilidades ----------
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const $ = s => document.querySelector(s);
  function aviso(texto, boton, accion) {
    const t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = `<span>${esc(texto)}</span>` + (boton ? `<button type="button">${esc(boton)}</button>` : '');
    if (boton) t.querySelector('button').onclick = accion;
    document.body.appendChild(t);
    if (!boton) setTimeout(() => t.remove(), 3500);
  }

  // ---------- modo sin internet ----------
  if ('serviceWorker' in navigator) {
    const yaHabia = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.register('sw.js').catch(() => {});
    // Cuando llega una versión nueva (por ejemplo, agregaste un banco), avisar para recargar.
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (yaHabia) aviso('Hay una versión nueva de la app.', 'Actualizar', () => location.reload());
    });
  }
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});

  return { cargar, guardar, cargarHtml, resumen, exportar, importar, esc, $, aviso };
})();

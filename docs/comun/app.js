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

  // ---------- registro de respuestas (para estadísticas) ----------
  // pwa:registro = lista de [id 'banco|pregunta', fecha (ms), tiempo (ms), acertó (1/0/-1 sin clave), primer intento (1/0)]
  const REG = 'registro';
  function registro() {
    try { const r = JSON.parse(localStorage.getItem(PREF + REG)); if (Array.isArray(r)) return r; } catch (e) {}
    return [];
  }
  function anotar(id, ms, ok, primera) {
    const r = registro();
    r.push([id, Date.now(), Math.max(0, Math.min(Math.round(ms || 0), 15 * 60000)), ok === true ? 1 : ok === false ? 0 : -1, primera ? 1 : 0]);
    try { localStorage.setItem(PREF + REG, JSON.stringify(r)); } catch (e) {}
  }
  // pwa:simulacros = resultados de los simulacros terminados
  function simulacros() {
    try { const r = JSON.parse(localStorage.getItem(PREF + 'simulacros')); if (Array.isArray(r)) return r; } catch (e) {}
    return [];
  }
  function guardarSimulacro(x) {
    const r = simulacros(); r.push(x);
    try { localStorage.setItem(PREF + 'simulacros', JSON.stringify(r)); } catch (e) {}
  }
  // Sesiones a medias (para "continuar donde me quedé")
  function sesiones() {
    const out = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (!k || !k.startsWith(PREF) || k === PREF + REG || k === PREF + 'simulacros') continue;
      let d; try { d = JSON.parse(localStorage.getItem(k)); } catch (e) { continue; }
      const s = d && d.ses;
      if (!s || !s.ids || !s.ids.length) continue;
      const id = k.slice(PREF.length);
      let url = s.url, nombre = s.nombre;
      if (!url) {
        if (id.startsWith('tema-')) url = 'banco.html?tema=' + encodeURIComponent(id.slice(5));
        else url = 'banco.html?id=' + encodeURIComponent(id);
      }
      out.push({ id, url: url + (url.includes('?') ? '&' : '?') + 'continuar=1', nombre: nombre || id, ses: s });
    }
    return out.sort((a, b) => (b.ses.ts || 0) - (a.ses.ts || 0));
  }

  // ---------- cronograma ----------
  const semanasDe = t => t.semana == null ? [] : [].concat(t.semana);
  const dia = f => new Date(f + 'T00:00:00');
  function semanaActual(crono, hoy = new Date()) {
    if (!crono) return null;
    const h = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
    for (const s of crono.semanas) {
      const ini = dia(s.inicio), fin = dia(s.fin);
      const finSemana = new Date(fin); finSemana.setDate(finSemana.getDate() + 2);   // sáb y dom cuentan como "la siguiente"
      if (h >= ini && h <= fin) return { s, estado: 'en curso' };
      if (h > fin && h <= finSemana) { const sig = crono.semanas.find(x => x.n === s.n + 1); return sig ? { s: sig, estado: 'empieza' } : { s, estado: 'en curso' }; }
    }
    if (h < dia(crono.semanas[0].inicio)) return { s: crono.semanas[0], estado: 'empieza' };
    return null;
  }

  // ---------- todas las preguntas (para temas, semanas y estadísticas) ----------
  let _todas = null;
  function todas(cat) {
    if (_todas) return _todas;
    const bancos = cat.bancos.filter(b => b.n);
    _todas = Promise.all(bancos.map(b => fetch('datos/' + encodeURIComponent(b.id) + '.json').then(r => r.json()).catch(() => null)))
      .then(datos => {
        const qs = [];
        datos.forEach((d, i) => d && d.preguntas.forEach(q => qs.push(Object.assign({}, q, { gid: bancos[i].id + '|' + q.id, banco: bancos[i].id, bn: bancos[i].nombre }))));
        return qs;
      });
    return _todas;
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

  return { cargar, guardar, cargarHtml, resumen, exportar, importar, esc, $, aviso,
    registro, anotar, simulacros, guardarSimulacro, sesiones, semanasDe, semanaActual, dia, todas };
})();

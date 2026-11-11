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

  // ---------- ajustes (meta diaria y tema) ----------
  // pwa:ajustes = { meta: 30, tema: 'auto' | 'light' | 'dark', vibrar: true }
  const AJ = 'ajustes';
  function ajustes() {
    let a = {};
    try { a = JSON.parse(localStorage.getItem(PREF + AJ)) || {}; } catch (e) {}
    return { meta: Number.isFinite(+a.meta) && +a.meta > 0 ? Math.round(+a.meta) : 30, tema: a.tema === 'light' || a.tema === 'dark' ? a.tema : 'auto', vibrar: a.vibrar !== false };
  }
  function guardarAjustes(cambios) {
    const a = Object.assign(ajustes(), cambios);
    try { localStorage.setItem(PREF + AJ, JSON.stringify(a)); } catch (e) {}
    return a;
  }
  // "auto" = sin atributo data-theme (manda el modo del teléfono o la computadora)
  function aplicarTema(t) {
    const el = document.documentElement;
    if (t === 'light' || t === 'dark') el.setAttribute('data-theme', t); else el.removeAttribute('data-theme');
    const oscuro = t === 'dark' || (t !== 'light' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
    const m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', oscuro ? '#0B1C33' : '#1E5FA8');
  }
  function fijarTema(t) { guardarAjustes({ tema: t }); aplicarTema(t); }
  aplicarTema(ajustes().tema);
  if (window.matchMedia) {
    const mq = matchMedia('(prefers-color-scheme: dark)');
    const cambio = () => { if (ajustes().tema === 'auto') aplicarTema('auto'); };
    if (mq.addEventListener) mq.addEventListener('change', cambio); else if (mq.addListener) mq.addListener(cambio);
  }

  // vibración corta (no existe en iPhone: si no hay soporte, no pasa nada)
  function vibrar(patron) {
    try { if (navigator.vibrate && ajustes().vibrar) navigator.vibrate(patron); } catch (e) {}
  }

  // ---------- días, meta diaria y racha ----------
  const diaIni = (t, mas = 0) => { const d = new Date(t); d.setHours(0, 0, 0, 0); if (mas) d.setDate(d.getDate() + mas); return d.getTime(); };
  // respuestas de hoy frente a la meta, y días seguidos cumpliéndola (si hoy aún no, cuenta la racha de ayer)
  function metaEstado(r) {
    r = r || registro();
    const meta = ajustes().meta, cuenta = {};
    r.forEach(x => { const k = diaIni(x[1]); cuenta[k] = (cuenta[k] || 0) + 1; });
    const h0 = diaIni(Date.now()), hoy = cuenta[h0] || 0, cumplida = hoy >= meta;
    let racha = 0, d = cumplida ? h0 : diaIni(h0, -1);
    while ((cuenta[d] || 0) >= meta) { racha++; d = diaIni(d, -1); }
    return { meta, hoy, cumplida, racha };
  }

  // ---------- repaso espaciado ----------
  // Se calcula solo, a partir de pwa:registro. Racha = aciertos seguidos contando desde la última respuesta.
  // Falló la última -> mañana · racha 1 -> 3 días · 2 -> 7 · 3 -> 14 · 4 o más -> 30.
  function mapaRegistro() {
    const m = {};
    registro().forEach(r => { if (r[3] < 0) return; (m[r[0]] = m[r[0]] || []).push(r); });
    Object.values(m).forEach(l => l.sort((a, b) => a[1] - b[1]));
    return m;
  }
  function programa(rs) {
    let racha = 0;
    for (let i = rs.length - 1; i >= 0 && rs[i][3] === 1; i--) racha++;
    const ult = rs[rs.length - 1], fallo = ult[3] === 0;
    const dias = fallo ? 1 : racha === 1 ? 3 : racha === 2 ? 7 : racha === 3 ? 14 : 30;
    return { racha, fallo, dias, due: diaIni(ult[1], dias) };
  }
  // ids 'banco|pregunta' -> { racha, fallo, dias, due } (solo las que tienen respuestas con clave)
  function programas(ids) {
    const m = mapaRegistro(), out = {};
    ids.forEach(id => { if (m[id]) out[id] = programa(m[id]); });
    return out;
  }
  // preguntas = lista de { banco, id, gid? } (por ejemplo, la de todas())
  function repaso(preguntas) {
    const m = mapaRegistro(), alm = {}, de = b => alm[b] || (alm[b] = cargar(b));
    const h0 = diaIni(Date.now());
    const out = { hoy: [], manana: 0, semana: 0, dominadas: 0, programadas: 0 };
    preguntas.forEach(q => {
      const gid = q.gid || (q.banco + '|' + q.id), a = de(q.banco), rs = m[gid];
      let due, racha = 0, fallo;
      if (rs) { const e = programa(rs); due = e.due; racha = e.racha; fallo = e.fallo; }
      else {                                   // historial viejo, sin registro
        const h = a.hist[q.id];
        if (!h || h.last !== false) return;
        due = h0; fallo = true;
      }
      out.programadas++;
      if (racha >= 3) out.dominadas++;
      const dd = Math.round((due - h0) / 864e5);
      if (dd <= 0) out.hoy.push({ q, gid, due, atraso: -dd, racha, marcada: !!(a.flag && a.flag[q.id]) && fallo });
      else if (dd === 1) out.manana++;
      else if (dd <= 7) out.semana++;
    });
    out.hoy.sort((x, y) => (y.marcada - x.marcada) || (y.atraso - x.atraso));
    return out;
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
    registro, anotar, ajustes, guardarAjustes, vibrar, fijarTema, aplicarTema, metaEstado, repaso, programas, simulacros, guardarSimulacro, sesiones, semanasDe, semanaActual, dia, todas };
})();

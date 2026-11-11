#!/usr/bin/env python3
"""Arma la app a partir de la carpeta originales/.

Uso (desde la carpeta app-bancos):   python3 herramientas/construir.py

Qué hace:
  1. Busca en originales/ archivos o carpetas que aún no estén en bancos.json y los agrega.
  2. Convierte cada banco:
       - .html interactivo  -> se copia a docs/bancos/<id>/ y se adapta (fuentes locales, botón Menú,
                               continuar sesión).
       - .pdf con texto     -> se extraen las preguntas y la clave (resaltado) a docs/datos/<id>.json
       - fotos o PDF escaneado -> OCR (reconocimiento de texto) -> docs/datos/<id>.json
       - "biblioteca"       -> cada página se guarda como imagen para leerla sin internet.
  3. Escribe docs/datos/catalogo.json (lo que muestra el menú) y docs/sw.js (lista para modo sin internet).

Solo usa herramientas que ya trae macOS (Python 3, Swift, PDFKit, Vision). No necesita internet,
salvo para descargar fuentes de Google de un banco HTML nuevo.
"""
import hashlib, json, os, re, shutil, subprocess, sys, unicodedata, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = os.path.join(RAIZ, 'originales')
DOCS = os.path.join(RAIZ, 'docs')
HERR = os.path.join(RAIZ, 'herramientas')
BIN = os.path.join(HERR, '.bin')
CACHE = os.path.join(HERR, '.cache')
CONFIG = os.path.join(RAIZ, 'bancos.json')
IMG = ('.jpg', '.jpeg', '.png', '.heic')

sys.path.insert(0, HERR)
from lineas_a_preguntas import parse  # noqa: E402
import verificar  # noqa: E402
import repetidas  # noqa: E402

# Si una pregunta está en varios bancos, se queda en el primero de esta lista (los demás la pierden)
PRIORIDAD = ['semana1', 'examenes-2026', 'fotos', 'pretest-2024', 'final-2021', 'recopilacion-2021',
             'simulacros', 'cicatrizacion', 'banco-traducido', 'lozano']
TEMAS = json.load(open(os.path.join(RAIZ, 'temas.json'), encoding='utf8'))
TEMAS_ASIGNADOS = os.path.join(RAIZ, 'verificacion', 'temas.json')
HTML_IDS = set()   # k -> tema (clasificación previa)


def slug(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:40] or 'banco'


def nombre_bonito(archivo):
    n = os.path.splitext(archivo)[0]
    n = re.sub(r'_\d{6}_\d{6}.*$', '', n)            # sufijos de fecha tipo _260518_173208
    n = re.sub(r'\s*\(\d+\)', '', n)                  # (1) (2)
    n = n.replace('_', ' ').strip()
    return n[:1].upper() + n[1:].lower() if n.isupper() else n


def herramienta(nombre):
    """Compila (una sola vez) la herramienta Swift y devuelve la ruta del ejecutable."""
    os.makedirs(BIN, exist_ok=True)
    src, exe = os.path.join(HERR, nombre + '.swift'), os.path.join(BIN, nombre)
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        print(f'  compilando {nombre}.swift (solo la primera vez)...')
        subprocess.run(['swiftc', '-O', src, '-o', exe], check=True, stderr=subprocess.DEVNULL)
    return exe


def huella(rutas, extra=''):
    h = hashlib.sha1(extra.encode())
    for r in rutas:
        st = os.stat(r)
        h.update(f'{r}|{st.st_size}|{int(st.st_mtime)}'.encode())
    return h.hexdigest()[:16]


def chars_por_pagina(pdf):
    """Para decidir si un PDF tiene texto o es escaneado (necesita OCR)."""
    out = os.path.join(CACHE, 'prueba-' + slug(pdf) + '.json')
    subprocess.run([herramienta('extraer_pdf'), pdf, out], check=True, capture_output=True)
    d = json.load(open(out, encoding='utf8'))
    os.remove(out)
    return sum(len(l['t']) for l in d['lines']) / max(1, d['pages']), d


# ---------- descubrir archivos nuevos ----------
def descubrir(cfg):
    usados = set()
    for b in cfg['bancos'] + cfg['biblioteca']:
        usados.update(b['archivos'])
        if b.get('carpeta'):
            usados.add(b['carpeta'])
    nuevos = []
    for f in sorted(os.listdir(ORIG)):
        if f.startswith('.') or f in usados:
            continue
        ruta = os.path.join(ORIG, f)
        if os.path.isdir(ruta):
            nuevos.append({'id': slug(f), 'nombre': f, 'tipo': 'fotos', 'carpeta': f, 'archivos': []})
        elif f.lower().endswith(('.html', '.htm')):
            nuevos.append({'id': slug(nombre_bonito(f)), 'nombre': nombre_bonito(f), 'tipo': 'html', 'archivos': [f]})
        elif f.lower().endswith('.pdf'):
            nuevos.append({'id': slug(nombre_bonito(f)), 'nombre': nombre_bonito(f), 'tipo': 'pdf', 'archivos': [f]})
        elif f.lower().endswith(IMG):
            print(f'  ⚠ {f}: las fotos sueltas van dentro de una carpeta (una carpeta = un banco). Se ignora.')
    ids = {b['id'] for b in cfg['bancos'] + cfg['biblioteca']}
    for n in nuevos:
        while n['id'] in ids:
            n['id'] += '-2'
        ids.add(n['id'])
        cfg['bancos'].append(n)
        print(f'  + nuevo: "{n["nombre"]}" ({n["tipo"]})')
    return bool(nuevos)


def archivos_de(b):
    if b.get('carpeta'):
        d = os.path.join(ORIG, b['carpeta'])
        fs = sorted(f for f in os.listdir(d) if f.lower().endswith(IMG + ('.pdf',)) and not f.startswith('.'))
        return [os.path.join(d, f) for f in fs]
    return [os.path.join(ORIG, f) for f in b['archivos']]


def seccion_de(b, ruta):
    base = os.path.basename(ruta)
    for pref, nombre in (b.get('secciones') or {}).items():
        if base.startswith(pref):
            return nombre
    return nombre_bonito(base) if b.get('secciones') is not None else None


# ---------- bancos PDF / fotos ----------
def lineas(ruta, ocr):
    """Extrae líneas (con caché, para no repetir el trabajo si el archivo no cambió)."""
    clave = huella([ruta], 'ocr' if ocr else 'txt')
    cache = os.path.join(CACHE, clave + '.json')
    if not os.path.exists(cache):
        print(f'    leyendo {os.path.basename(ruta)}' + (' (OCR, puede tardar)' if ocr else ''))
        if ocr:
            subprocess.run([herramienta('ocr'), cache, ruta], check=True, capture_output=True)
        else:
            subprocess.run([herramienta('extraer_pdf'), ruta, cache], check=True, capture_output=True)
    return json.load(open(cache, encoding='utf8'))


def construir_preguntas(b):
    rutas = archivos_de(b)
    preguntas, imgs, pagina0 = [], [], 0
    for ruta in rutas:
        es_foto = ruta.lower().endswith(IMG)
        ocr = es_foto or b.get('ocr', False)
        if not ocr and ruta.lower().endswith('.pdf'):
            cpp, _ = chars_por_pagina(ruta)
            ocr = cpp < 60
        d = lineas(ruta, ocr)
        sec = seccion_de(b, ruta)
        qs = parse(d['lines'], b.get('temas'))
        for q in qs:
            q['_f'] = [os.path.relpath(ruta, ORIG), q['p']]   # archivo y página, para verificar contra el original
            q['p'] += pagina0
            if sec:
                q['sec'] = sec
        preguntas += qs
        pagina0 += d['pages']
        if ocr and b.get('ver_original', True):
            imgs.append(ruta)
    # id estable + clave verificada con los libros (verificacion/<id>.json), si ya se revisó
    preguntas = verificar.aplicar(b['id'], preguntas)
    datos = {'id': b['id'], 'nombre': b['nombre'], 'preguntas': preguntas}
    if imgs:
        # Fotos/escaneos: se guardan reducidas para poder "ver el original" de cada pregunta.
        dest = os.path.join(DOCS, 'originales', b['id'])
        shutil.rmtree(dest, ignore_errors=True); os.makedirs(dest)
        n = subprocess.run([herramienta('paginas'), dest, '1300'] + imgs, check=True,
                           capture_output=True, text=True).stdout.strip()
        # p (página global) -> imagen; solo vale si todas las fuentes tienen imágenes
        if len(imgs) == len(rutas):
            datos['imgs'] = [f'originales/{b["id"]}/{i:03d}.jpg' for i in range(1, int(n) + 1)]
    else:
        # Sin "ver el original": se borran fotos publicadas antes de este banco.
        shutil.rmtree(os.path.join(DOCS, 'originales', b['id']), ignore_errors=True)
    return datos


def construir_json(b):
    """Banco que ya viene estructurado: originales/<archivo>.json = {"preguntas":[{stem, opts, ans, sec, n}]}.
    No hay imagen de página, así que no hay "ver el original"."""
    ruta = archivos_de(b)[0]
    preguntas = []
    for q in json.load(open(ruta, encoding='utf8'))['preguntas']:
        x = {'stem': q['stem'], 'opts': q['opts'], 'ans': q.get('ans'), 'p': q.get('n', 1)}
        if q.get('sec'):
            x['sec'] = q['sec']
        preguntas.append(x)
    shutil.rmtree(os.path.join(DOCS, 'originales', b['id']), ignore_errors=True)
    return {'id': b['id'], 'nombre': b['nombre'], 'preguntas': verificar.aplicar(b['id'], preguntas)}


def escribir_banco(b, datos):
    preguntas = datos['preguntas']
    with open(os.path.join(DOCS, 'datos', b['id'] + '.json'), 'w', encoding='utf8') as f:
        json.dump(datos, f, ensure_ascii=False, separators=(',', ':'))
    con = sum(q['ans'] is not None for q in preguntas)
    secs = sorted({q['sec'] for q in preguntas if q.get('sec')})
    ver = sum(q.get('ver', {}).get('e') in ('confirmada', 'corregida', 'nueva') for q in preguntas)
    alto = sum(1 for q in preguntas if q.get('rep'))
    return {'n': len(preguntas), 'conClave': con, 'secciones': len(secs), 'verificadas': ver, 'altoValor': alto}


def preguntas_html(b):
    """Las preguntas de un banco HTML (const Q = [...]) en el formato común, para repetidas y temas."""
    s = open(os.path.join(DOCS, 'bancos', b['id'], 'index.html'), encoding='utf8').read()
    m = re.search(r'const Q = (\[.*?\]);\n', s, re.S)
    if not m:
        return []
    salida = []
    for q in json.loads(m.group(1)):
        x = {'id': str(q['id']), 'stem': q['stem'], 'opts': q['opts'], 'ans': q.get('ans'), 'p': 0}
        if q.get('why'):
            x['why'] = q['why']
        salida.append(x)
    return salida


def unir_bancos(lista):
    """lista: [(b, datos)]. Quita las copias de una misma pregunta (se queda en el banco con más
    prioridad), marca como alto valor las que se repiten y pone el tema a cada pregunta."""
    global HTML_IDS
    HTML_IDS = {b['id'] for b, _ in lista if b['tipo'] == 'html'}
    orden = sorted(lista, key=lambda x: PRIORIDAD.index(x[0]['id']) if x[0]['id'] in PRIORIDAD else len(PRIORIDAD))
    nombres = {b['id']: b['nombre'] for b, _ in orden}
    grupos = repetidas.grupos([(b['id'], d['preguntas']) for b, d in orden])
    porid = {b['id']: d['preguntas'] for b, d in orden}
    quitar = set()
    for g in grupos:
        bancos_g = []
        for bid, i, _ in g:
            if nombres[bid] not in bancos_g:
                bancos_g.append(nombres[bid])
        rep = {'n': len(g), 'en': bancos_g}
        # de las copias idénticas se conserva una: la verificada con libro si la hay, si no la del banco prioritario
        copias = [(bid, i) for bid, i, tipo in g if tipo in ('base', 'misma')]
        verif = [c for c in copias if porid[c[0]][c[1]].get('ver') and nombres[c[0]] and c[0] not in HTML_IDS]
        queda = verif[0] if verif else copias[0]
        for bid, i, tipo in g:
            if tipo in ('base', 'misma') and (bid, i) != queda:
                quitar.add((bid, i))
            else:
                porid[bid][i]['rep'] = rep
    asignados = json.load(open(TEMAS_ASIGNADOS, encoding='utf8')) if os.path.exists(TEMAS_ASIGNADOS) else {}
    validos = {t['id'] for t in TEMAS}
    for b, d in orden:
        d['preguntas'] = [q for i, q in enumerate(d['preguntas']) if (b['id'], i) not in quitar]
        for q in d['preguntas']:
            t = q.get('tema') or asignados.get(f"{b['id']}:{q['id']}")
            if t in validos:
                q['tema'] = t
            else:
                q.pop('tema', None)
    print(f'Repetidas: {len(quitar)} copias quitadas · {len(grupos)} preguntas o temas que se repiten (alto valor)')


# ---------- bancos HTML ----------
FUENTES_CSS = os.path.join(DOCS, 'fuentes', 'fuentes.css')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'


def descargar(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=30).read()


def fuentes_locales(url_css):
    """Descarga una hoja de Google Fonts (solo alfabetos latinos) y la agrega a docs/fuentes/fuentes.css."""
    actual = open(FUENTES_CSS, encoding='utf8').read() if os.path.exists(FUENTES_CSS) else ''
    marca = f'/* origen: {url_css} */'
    if marca in actual:
        return
    css = descargar(url_css).decode('utf8')
    bloques = re.findall(r'/\* ([a-z-]+) \*/\s*(@font-face\s*\{[^}]*\})', css)
    salida = [marca]
    for subset, bloque in bloques:
        if subset not in ('latin', 'latin-ext'):
            continue
        url = re.search(r'url\((https://[^)]+)\)', bloque).group(1)
        fam = slug(re.search(r"font-family:\s*'([^']+)'", bloque).group(1))
        nombre = f'{fam}-{hashlib.sha1(url.encode()).hexdigest()[:8]}.woff2'
        destino = os.path.join(DOCS, 'fuentes', nombre)
        if not os.path.exists(destino):
            open(destino, 'wb').write(descargar(url))
        salida.append(f'/* {subset} */\n' + bloque.replace(url, nombre))
    open(FUENTES_CSS, 'a', encoding='utf8').write('\n'.join(salida) + '\n')


CABECERA_PWA = '''<link rel="manifest" href="../../manifest.webmanifest">
<meta name="theme-color" content="#1E5FA8">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Bancos Cx">
<link rel="apple-touch-icon" href="../../iconos/apple-touch-icon.png">
<link rel="stylesheet" href="../../comun/integrar.css">
'''
BARRA = '<nav class="pwa-barra"><a href="../../index.html">← Menú</a><span id="pwa-titulo"></span></nav>\n'
PIE = '<script src="../../comun/integrar.js"></script>\n'

# Parches para bancos HTML hechos con el mismo formato que "Banco Semana 1".
# Si un banco nuevo tiene otro formato, simplemente no se aplican (el banco igual funciona).
PARCHES = [
    # guardar la sesión en curso cada vez que cambia la pregunta
    ("function renderQ(){", "function renderQ(){ guardarSesion();"),
    ("S.done=true; $('#quiz').hidden=true;", "S.done=true; delete store.ses; save(); $('#quiz').hidden=true;"),
    ("$('#quitBtn').addEventListener('click',()=>{ S=null;", "$('#quitBtn').addEventListener('click',()=>{ S=null; delete store.ses; save();"),
    ("const rh=$('#resetHist');", "botonContinuar(); const rh=$('#resetHist');"),
    ("/* ---------- inicio ---------- */", """/* ---------- continuar sesión (agregado para la app) ---------- */
function guardarSesion(){ if(S&&!S.done){ store.ses={ids:S.ids,i:S.i,ans:S.ans,locked:S.locked,t:S.t,mode:S.mode,ts:Date.now()}; save(); } }
function botonContinuar(){
  const viejo=$('#pwaContinuar'); if(viejo) viejo.remove();
  const s=store.ses; if(!s||!s.ids||!s.ids.length||!s.ids.every(id=>byId[id])) return;
  const r=document.createElement('div'); r.id='pwaContinuar'; r.className='start-row';
  r.innerHTML=`<button class="btn amber" type="button">Continuar donde me quedé · pregunta ${s.i+1} de ${s.ids.length}</button>`;
  r.querySelector('button').addEventListener('click',()=>{ S=Object.assign({},s,{enter:performance.now(),done:false});
    $('#setup').hidden=true; $('#results').hidden=true; $('#quiz').hidden=false; renderQ(); window.scrollTo({top:0}); });
  $('#setup').prepend(r);
}
/* ---------- inicio ---------- */"""),
    # los decks están en claude.ai: avisar que necesitan internet
    (">Abrir el deck</a>", ">Abrir el deck (requiere internet)</a>"),
    (">Abrir el deck de la clase ${t.n}</a>", ">Abrir el deck de la clase ${t.n} (requiere internet)</a>"),
]


def construir_html(b):
    ruta = archivos_de(b)[0]
    html = open(ruta, encoding='utf8').read()
    # 1. Google Fonts -> fuentes locales
    for url in re.findall(r'<link[^>]+href="(https://fonts\.googleapis\.com/css2?[^"]+)"', html):
        try:
            fuentes_locales(url.replace('&amp;', '&'))
        except Exception as e:  # sin internet: el banco usará las fuentes del sistema
            print(f'    ⚠ no pude descargar fuentes ({e}); se usarán las del sistema')
    html = re.sub(r'<link[^>]+(fonts\.googleapis\.com|fonts\.gstatic\.com)[^>]*>\s*', '', html)
    html = html.replace('</head>', '<link rel="stylesheet" href="../../fuentes/fuentes.css">\n' + CABECERA_PWA + '</head>', 1)
    # 2. otros recursos externos (scripts, estilos, imágenes de CDN) -> copia local
    ext_dir = os.path.join(DOCS, 'bancos', b['id'], 'ext')
    for url in sorted(set(re.findall(r'(?:src|href)="(https?://[^"]+\.(?:js|css|png|jpe?g|svg|gif|webp|woff2?))"', html))):
        try:
            os.makedirs(ext_dir, exist_ok=True)
            nombre = hashlib.sha1(url.encode()).hexdigest()[:10] + '-' + os.path.basename(url.split('?')[0])
            open(os.path.join(ext_dir, nombre), 'wb').write(descargar(url))
            html = html.replace(url, 'ext/' + nombre)
            print(f'    descargado para uso sin internet: {url}')
        except Exception as e:
            print(f'    ⚠ no pude descargar {url}: {e}')
    # 3. parches de progreso
    aplicados = 0
    for viejo, nuevo in PARCHES:
        if viejo in html:
            html = html.replace(viejo, nuevo, 1); aplicados += 1
    # 4. barra superior con botón Menú + script de integración
    html = re.sub(r'(<body[^>]*>)', r'\1\n' + BARRA, html, count=1)
    html = html.replace('</body>', PIE + '</body>', 1)
    dest = os.path.join(DOCS, 'bancos', b['id'])
    os.makedirs(dest, exist_ok=True)
    open(os.path.join(dest, 'index.html'), 'w', encoding='utf8').write(html)
    # estadísticas: cuántas preguntas y dónde guarda el progreso
    n = None
    m = re.search(r'const Q\s*=\s*(\[.*?\]);\s*\n', html, re.S)
    if m:
        try:
            n = len(json.loads(m.group(1)))
        except ValueError:
            pass
    k = re.search(r"const KEY\s*=\s*'([^']+)'", html)
    print(f'    {aplicados}/{len(PARCHES)} adaptaciones aplicadas')
    return {'n': n, 'conClave': n, 'clave': k.group(1) if k else None}


# ---------- biblioteca ----------
def construir_biblioteca(b):
    rutas = archivos_de(b)
    dest = os.path.join(DOCS, 'biblioteca', b['id'])
    shutil.rmtree(dest, ignore_errors=True); os.makedirs(dest)
    print(f'    convirtiendo páginas de {", ".join(os.path.basename(r) for r in rutas)}')
    n = int(subprocess.run([herramienta('paginas'), dest, '1100'] + rutas, check=True,
                           capture_output=True, text=True).stdout.strip())
    return {'paginas': n}


# ---------- service worker ----------
def escribir_sw():
    """Lista todo lo que se guarda para uso sin internet. La biblioteca se guarda al abrirla
    (o con el botón 'Descargar todo') para no llenar el celular de golpe."""
    archivos = []
    for base, dirs, fs in os.walk(DOCS):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in fs:
            rel = os.path.relpath(os.path.join(base, f), DOCS).replace(os.sep, '/')
            if f.startswith('.') or rel == 'sw.js' or rel.startswith('biblioteca/') or rel.endswith('google.css'):
                continue
            archivos.append(rel)
    archivos.sort()
    h = hashlib.sha1()
    for rel in archivos:
        h.update(rel.encode()); h.update(open(os.path.join(DOCS, rel), 'rb').read())
    version = h.hexdigest()[:10]
    plantilla = open(os.path.join(HERR, 'sw.plantilla.js'), encoding='utf8').read()
    sw = plantilla.replace('__VERSION__', version).replace('__ARCHIVOS__', json.dumps(['./'] + archivos, indent=1))
    open(os.path.join(DOCS, 'sw.js'), 'w', encoding='utf8').write(sw)
    return version, len(archivos)


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(os.path.join(DOCS, 'datos'), exist_ok=True)
    cfg = json.load(open(CONFIG, encoding='utf8')) if os.path.exists(CONFIG) else {'bancos': [], 'biblioteca': []}
    print('Buscando archivos nuevos en originales/ ...')
    descubrir(cfg)

    catalogo = {'bancos': [], 'biblioteca': []}
    leidos, infos_html = [], {}
    for b in list(cfg['bancos']):
        print(f'• {b["nombre"]}')
        if b['tipo'] == 'html':
            infos_html[b['id']] = construir_html(b)
            leidos.append((b, {'id': b['id'], 'nombre': b['nombre'], 'preguntas': preguntas_html(b)}))
        else:
            datos = construir_json(b) if b['tipo'] == 'json' else construir_preguntas(b)
            if len(datos['preguntas']) < 5 and b.get('auto', True):
                # casi sin preguntas: es un resumen -> pasa a la biblioteca
                print(f'    solo {len(datos["preguntas"])} preguntas: lo paso a la Biblioteca')
                cfg['bancos'].remove(b); b['tipo'] = 'biblioteca'; cfg['biblioteca'].append(b)
                continue
            leidos.append((b, datos))
    unir_bancos(leidos)
    # Copia completa de cada banco (con o sin verificar): la usan las herramientas de verificación y temas
    os.makedirs(verificar.FUENTES, exist_ok=True); os.makedirs(verificar.COMPLETO, exist_ok=True)
    for b, datos in leidos:
        with open(os.path.join(verificar.FUENTES, b['id'] + '.json'), 'w', encoding='utf8') as f:
            json.dump({q['id']: q.pop('_f') for q in datos['preguntas'] if '_f' in q}, f, ensure_ascii=False)
        with open(os.path.join(verificar.COMPLETO, b['id'] + '.json'), 'w', encoding='utf8') as f:
            json.dump(datos, f, ensure_ascii=False, separators=(',', ':'))
    if cfg.get('solo_verificadas'):
        # bancos.json -> "solo_verificadas": true  =  la app muestra solo preguntas con clave verificada con libro
        for _, datos in leidos:
            datos['preguntas'] = [q for q in datos['preguntas'] if q.get('ver', {}).get('e') in ('confirmada', 'corregida', 'nueva')]
        leidos = [(b, d) for b, d in leidos if d['preguntas']]
        print(f'Solo verificadas: {sum(len(d["preguntas"]) for _, d in leidos)} preguntas en {len(leidos)} bancos')
    for b, datos in leidos:
        if b['tipo'] == 'html':
            # sus preguntas también van a datos/, para estudiar por tema (el banco se sigue abriendo en su HTML)
            extra = escribir_banco(b, datos)
            info = dict(infos_html[b['id']], altoValor=extra['altoValor'])
            catalogo['bancos'].append({'id': b['id'], 'nombre': b['nombre'], 'tipo': 'html',
                                       'url': f'bancos/{b["id"]}/index.html', **info})
        else:
            info = escribir_banco(b, datos)
            catalogo['bancos'].append({'id': b['id'], 'nombre': b['nombre'], 'tipo': 'preguntas',
                                       'url': f'banco.html?id={b["id"]}', **info,
                                       **({'destacado': True} if b.get('destacado') else {})})
        print(f'  {b["nombre"]}: {info["n"]} preguntas' + (f', {info["conClave"]} con clave' if b['tipo'] != 'html' else '')
              + (f', {info.get("verificadas")} verificadas' if info.get('verificadas') else ''))
    # temas: cuántas preguntas hay de cada uno, entre todos los bancos
    cuenta = {}
    for _, datos in leidos:
        for q in datos['preguntas']:
            if q.get('tema'):
                c = cuenta.setdefault(q['tema'], {'n': 0, 'alto': 0})
                c['n'] += 1; c['alto'] += bool(q.get('rep'))
    catalogo['temas'] = [dict(id=t['id'], nombre=t['nombre'], clase=t['clase'], semana=t.get('semana'), **cuenta[t['id']])
                         for t in TEMAS if t['id'] in cuenta]
    # cronograma del curso (semanas y fechas de examen): lo usa el menú para agrupar los temas por semana
    crono = os.path.join(RAIZ, 'cronograma.json')
    if os.path.exists(crono):
        catalogo['cronograma'] = json.load(open(crono, encoding='utf8'))
    catalogo['sinTema'] = sum(1 for _, d in leidos for q in d['preguntas'] if not q.get('tema'))
    for b in cfg['biblioteca']:
        print(f'• (biblioteca) {b["nombre"]}')
        clave = huella(archivos_de(b))
        hecho = os.path.join(DOCS, 'biblioteca', b['id'], '.huella')
        if os.path.exists(hecho) and open(hecho).read() == clave:
            info = {'paginas': len([f for f in os.listdir(os.path.dirname(hecho)) if f.endswith('.jpg')])}
        else:
            info = construir_biblioteca(b)
            open(hecho, 'w').write(clave)
        catalogo['biblioteca'].append({'id': b['id'], 'nombre': b['nombre'], **info})

    # quitar datos de bancos que ya no existen
    vivos = {b['id'] for b in catalogo['bancos']}
    for f in os.listdir(os.path.join(DOCS, 'datos')):
        if f.endswith('.json') and f != 'catalogo.json' and f[:-5] not in vivos:
            os.remove(os.path.join(DOCS, 'datos', f))

    json.dump(cfg, open(CONFIG, 'w', encoding='utf8'), ensure_ascii=False, indent=2)
    json.dump(catalogo, open(os.path.join(DOCS, 'datos', 'catalogo.json'), 'w', encoding='utf8'),
              ensure_ascii=False, indent=1)
    version, n = escribir_sw()
    total = sum(b['n'] or 0 for b in catalogo['bancos'])
    print(f'\nListo: {len(catalogo["bancos"])} bancos, {total} preguntas, '
          f'{len(catalogo["biblioteca"])} documentos en la biblioteca. Versión {version} ({n} archivos para uso sin internet).')


if __name__ == '__main__':
    main()

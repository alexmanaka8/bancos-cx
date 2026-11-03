#!/usr/bin/env python3
"""Verificación de claves con los libros (ver verificacion/REGLAS.md).

  python3 herramientas/verificar.py lotes <banco> [--tam 20]   # reparte lo pendiente en lotes
  python3 herramientas/verificar.py original <banco> <k>       # imagen de la página original de una pregunta
  python3 herramientas/verificar.py validar <archivo.json>     # revisa que un resultado esté bien armado
  python3 herramientas/verificar.py unir <banco>               # junta los resultados en verificacion/<banco>.json
  python3 herramientas/verificar.py estado                     # cuánto falta por banco

construir.py usa aplicar() para poner en la app la clave verificada, la explicación y la fuente.
"""
import glob, hashlib, json, os, re, subprocess, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
VER = os.path.join(RAIZ, 'verificacion')
DATOS = os.path.join(RAIZ, 'docs', 'datos')
FUENTES = os.path.join(AQUI, '.cache', 'fuentes')
COMPLETO = os.path.join(AQUI, '.cache', 'completo')   # bancos completos, aunque la app muestre solo verificadas
ESTADOS = ('confirmada', 'corregida', 'nueva', 'dudosa', 'anulada')
TEMAS = [t['id'] for t in json.load(open(os.path.join(RAIZ, 'temas.json'), encoding='utf8'))]


def _norm(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if c.isalnum() or c == ' ')
    return ' '.join(s.split())


def clave(q):
    """Identificador estable de una pregunta (no cambia si se reordena el banco)."""
    base = _norm(q['stem']) + '|' + '|'.join(_norm(o) for o in q['opts'])
    return hashlib.sha1(base.encode()).hexdigest()[:10]


def registros(banco):
    ruta = os.path.join(VER, banco + '.json')
    return json.load(open(ruta, encoding='utf8')) if os.path.exists(ruta) else {}


def _con_verificacion(q, r):
    q = dict(q, stem=r['stem'], opts=r['opts'], ans=r['ans'])
    q['ver'] = {'e': r['estado'], 'f': r.get('fuentes', [])}
    if r.get('why'):
        q['why'] = r['why']
    if r.get('nota'):
        q['ver']['n'] = r['nota']
    if r.get('tema'):
        q['tema'] = r['tema']
    return q


def aplicar(banco, preguntas):
    """Pone id estable a cada pregunta y, si ya fue verificada, su texto corregido, clave y explicación."""
    regs, salida, vistos = registros(banco), [], set()
    for q in preguntas:
        k = clave(q)
        if k in vistos:   # la misma pregunta en dos fotos o archivos
            continue
        vistos.add(k)
        r = regs.get(k)
        if not r:
            salida.append(dict(q, id=k))
            continue
        salida.append(dict(_con_verificacion(q, r), id=k))
        for j, extra in enumerate(r.get('dividir', []), 2):
            salida.append(dict(_con_verificacion(q, extra), id=f'{k}-{j}'))
    # preguntas del original que la extracción automática perdió (las agregó quien verificó)
    for k, r in regs.items():
        if r.get('agregada') and k not in vistos:
            pos = next((i + 1 for i, q in enumerate(salida) if q['id'] == r.get('despues_de')), len(salida))
            base = salida[pos - 1] if pos else {}
            nueva = {'stem': '', 'opts': [], 'ans': None, 'p': base.get('p', 1)}
            if base.get('sec'):
                nueva['sec'] = base['sec']
            if '_f' in base:
                nueva['_f'] = base['_f']
            salida.insert(pos, dict(_con_verificacion(nueva, r), id=k))
    return salida


def _datos(banco):
    d = json.load(open(os.path.join(COMPLETO, banco + '.json'), encoding='utf8'))
    f = json.load(open(os.path.join(FUENTES, banco + '.json'), encoding='utf8'))
    return d['preguntas'], f


def lotes(banco, tam=20, solo_alto=False):
    preguntas, fuentes = _datos(banco)
    hechos = set(registros(banco))
    for r in glob.glob(os.path.join(VER, 'resultados', banco, '*.json')):
        hechos |= {x['k'] for x in json.load(open(r, encoding='utf8'))}
    pend = [q for q in preguntas if q['id'] not in hechos and '-' not in q['id'] and q['id'] in fuentes
            and (q.get('rep') or not solo_alto)]
    carpeta = os.path.join(VER, 'lotes', banco)
    os.makedirs(carpeta, exist_ok=True)
    for f in glob.glob(os.path.join(carpeta, '*.json')):
        os.remove(f)
    # numerar después de los resultados que ya existen, para no pisarlos
    usados = [int(os.path.basename(f)[:3]) for f in glob.glob(os.path.join(VER, 'resultados', banco, '*.json'))]
    trozos = [pend[i:i + tam] for i in range(0, len(pend), tam)]
    for n, trozo in enumerate(trozos, max(usados, default=0) + 1):
        sig = trozos[n - max(usados, default=0)] if n - max(usados, default=0) < len(trozos) else None
        lote = {'banco': banco,
                'cubre_hasta': 'SOLO estas preguntas (lote de alto valor): no busques preguntas perdidas' if solo_alto else ({'archivo': fuentes[sig[0]['id']][0], 'pagina': fuentes[sig[0]['id']][1],
                                 'pregunta': sig[0]['stem'][:120]} if sig else 'fin del banco'),
                'preguntas': [{'k': q['id'], 'sec': q.get('sec'), 'stem': q['stem'], 'opts': q['opts'],
                               'clave_original': q['ans'], 'origen_clave': q.get('src'),
                               'archivo': fuentes[q['id']][0], 'pagina': fuentes[q['id']][1]} for q in trozo]}
        json.dump(lote, open(os.path.join(carpeta, f'{n:03d}.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(f'{banco}: {len(pend)} pendientes en {-(-len(pend) // tam)} lotes -> {carpeta}')


def original(banco, k):
    _, fuentes = _datos(banco)
    archivo, p = fuentes[k]
    ruta = os.path.join(RAIZ, 'originales', archivo)
    if not ruta.lower().endswith('.pdf'):
        print(ruta); return
    binario = os.path.join(AQUI, '.bin', 'pagina_png')
    fuente = os.path.join(AQUI, 'pagina_png.swift')
    if not os.path.exists(binario) or os.path.getmtime(binario) < os.path.getmtime(fuente):
        subprocess.run(['swiftc', '-O', fuente, '-o', binario], check=True)
    os.makedirs(os.path.join(VER, '.imagenes'), exist_ok=True)
    for pp in (p, p + 1):   # la pregunta puede seguir en la página siguiente
        out = os.path.join(VER, '.imagenes', f'{banco}-{k}-p{pp}.png')
        if subprocess.run([binario, ruta, str(pp), out], capture_output=True).returncode == 0:
            print(out)


def _errores_registro(r, donde):
    e = []
    if r.get('estado') not in ESTADOS:
        e.append(f'{donde}: estado debe ser uno de {ESTADOS}')
    if not isinstance(r.get('stem'), str) or len(r['stem'].strip()) < 10:
        e.append(f'{donde}: falta stem')
    if not isinstance(r.get('opts'), list) or len(r['opts']) < 2:
        e.append(f'{donde}: opts debe ser una lista de 2 o más')
    a = r.get('ans')
    if r.get('estado') in ('confirmada', 'corregida', 'nueva'):
        if not isinstance(a, int) or not 0 <= a < len(r.get('opts') or []):
            e.append(f'{donde}: ans debe ser el índice (0 = A) de una opción')
        if not r.get('fuentes'):
            e.append(f'{donde}: una clave verificada necesita fuentes')
    elif a is not None:
        e.append(f'{donde}: si está {r.get("estado")}, ans debe ser null')
    if not r.get('why') or len(r['why']) < 40:
        e.append(f'{donde}: falta explicación (why)')
    if r.get('tema') not in TEMAS:
        e.append(f'{donde}: tema debe ser uno de temas.json ({", ".join(TEMAS)})')
    return e


def validar(ruta):
    lista = json.load(open(ruta, encoding='utf8'))
    e = []
    for i, r in enumerate(lista):
        if not r.get('k'):
            e.append(f'#{i}: falta k')
        e += _errores_registro(r, f'#{i} ({r.get("k")})')
        for j, x in enumerate(r.get('dividir', [])):
            e += _errores_registro(x, f'#{i} dividir[{j}]')
    print('\n'.join(e) if e else f'OK: {len(lista)} preguntas')
    return not e


def unir(banco):
    regs = registros(banco)
    for ruta in sorted(glob.glob(os.path.join(VER, 'resultados', banco, '*.json'))):
        if validar(ruta):
            regs.update({r['k']: r for r in json.load(open(ruta, encoding='utf8'))})
    json.dump(regs, open(os.path.join(VER, banco + '.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(f'{banco}: {len(regs)} preguntas verificadas guardadas')


def estado():
    for f in sorted(glob.glob(os.path.join(COMPLETO, '*.json'))):
        banco = os.path.basename(f)[:-5]
        n = len(json.load(open(f, encoding='utf8'))['preguntas'])
        regs = registros(banco)
        c = {e: sum(r['estado'] == e for r in regs.values()) for e in ESTADOS}
        print(f'{banco:20} {len(regs):5}/{n:<5} ' + ' '.join(f'{e}={v}' for e, v in c.items() if v))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'lotes':
        lotes(a[1], int(a[a.index('--tam') + 1]) if '--tam' in a else 20, '--alto' in a)
    elif a[0] == 'original':
        original(a[1], a[2])
    elif a[0] == 'validar':
        sys.exit(0 if validar(a[1]) else 1)
    elif a[0] == 'unir':
        unir(a[1])
    elif a[0] == 'estado':
        estado()

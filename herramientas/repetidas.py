#!/usr/bin/env python3
"""Detecta preguntas repetidas entre bancos (y dentro de un mismo banco).

Dos preguntas son "la misma" si el enunciado y las opciones se parecen mucho, aunque cambie la
redacción, el orden de las opciones o haya errores de OCR. Las variantes (mismo enunciado con
opciones distintas) no se borran, pero también cuentan como tema que se repite.

  python3 herramientas/repetidas.py           # informe: cuántas hay y ejemplos dudosos
"""
import json, os, re, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

UMBRAL_ENUNCIADO = 0.72   # parecido mínimo del enunciado (Jaccard de palabras)
UMBRAL_OPCIONES = 0.55    # parecido mínimo de las opciones para considerarla la misma pregunta
VACIAS = set('''que del los las una por con para como cual cuál mas más este esta son sus ser
según segun entre sobre todo todas todos excepto incorrecta correcta siguiente siguientes
paciente años anos'''.split())


def palabras(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return {w for w in re.findall(r'[a-z0-9]+', s) if len(w) > 2 and w not in VACIAS}


NEGATIVA = re.compile(r'\b(excepto|salvo|incorrect[ao]s?|fals[ao]s?|no (es|corresponde|se|son|debe|constituye|incluye))\b', re.I)


def negativa(q):
    """'¿Cuál es correcta?' y '¿Cuál NO es correcta / EXCEPTO?' tienen respuestas opuestas."""
    return bool(NEGATIVA.search(unicodedata.normalize('NFC', q['stem'])))


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def opciones(q):
    return set().union(*(palabras(o) for o in q['opts'])) if q['opts'] else set()


def grupos(bancos):
    """bancos: lista de (id, [preguntas]) en orden de prioridad.
    Devuelve una lista de grupos; cada grupo es una lista de (banco, índice, tipo), donde tipo es
    'misma' o 'variante' respecto del primero del grupo, que es el que se conserva."""
    items = []
    for bid, qs in bancos:
        for i, q in enumerate(qs):
            items.append((bid, i, palabras(q['stem']), opciones(q), negativa(q)))
    # índice invertido: solo se comparan preguntas que comparten palabras poco frecuentes
    frec = {}
    for _, _, e, _, _ in items:
        for w in e:
            frec[w] = frec.get(w, 0) + 1
    indice = {}
    for n, (_, _, e, _, _) in enumerate(items):
        for w in sorted(e, key=lambda w: frec[w])[:6]:
            indice.setdefault(w, []).append(n)
    padre = list(range(len(items)))
    tipo = {}

    def raiz(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]; x = padre[x]
        return x
    for n, (_, _, e, o, neg) in enumerate(items):
        if len(e) < 4:
            continue   # enunciado demasiado corto para comparar con seguridad
        cand = set()
        for w in sorted(e, key=lambda w: frec[w])[:6]:
            cand.update(m for m in indice.get(w, []) if m < n)
        for m in cand:
            e2, o2, neg2 = items[m][2], items[m][3], items[m][4]
            if jaccard(e, e2) >= UMBRAL_ENUNCIADO:
                misma = jaccard(o, o2) >= UMBRAL_OPCIONES and neg == neg2
                a, b = raiz(m), raiz(n)
                if a != b:
                    padre[b] = a
                tipo[n] = 'misma' if misma or tipo.get(n) == 'misma' else tipo.get(n, 'variante')
    salida = {}
    for n in range(len(items)):
        salida.setdefault(raiz(n), []).append(n)
    res = []
    for r, ns in salida.items():
        if len(ns) > 1:
            ns.sort()
            res.append([(items[n][0], items[n][1], 'base' if k == 0 else tipo.get(n, 'variante')) for k, n in enumerate(ns)])
    return res


def cargar_todo():
    cfg = json.load(open(os.path.join(RAIZ, 'bancos.json'), encoding='utf8'))
    bancos = []
    for b in cfg['bancos']:
        if b['tipo'] == 'html':
            s = open(os.path.join(RAIZ, 'docs', 'bancos', b['id'], 'index.html'), encoding='utf8').read()
            m = re.search(r'const Q = (\[.*?\]);\n', s, re.S)
            qs = json.loads(m.group(1)) if m else []
        else:
            qs = json.load(open(os.path.join(RAIZ, 'docs', 'datos', b['id'] + '.json'), encoding='utf8'))['preguntas']
        bancos.append((b['id'], qs))
    return bancos


if __name__ == '__main__':
    bancos = cargar_todo()
    porid = dict(bancos)
    gs = grupos(bancos)
    mismas = sum(1 for g in gs for x in g if x[2] == 'misma')
    var = sum(1 for g in gs for x in g if x[2] == 'variante')
    print(f'{len(gs)} grupos de preguntas repetidas · {mismas} copias sobrantes · {var} variantes')
    for g in gs[:int(sys.argv[1]) if len(sys.argv) > 1 else 6]:
        print('---')
        for bid, i, t in g:
            q = porid[bid][i]
            print(f'  [{t}] {bid}: {q["stem"][:110]} | {" / ".join(o[:25] for o in q["opts"])[:110]}')

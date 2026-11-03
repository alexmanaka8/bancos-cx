#!/usr/bin/env python3
"""Clasificación por tema (del sílabo, temas.json) de las preguntas que aún no tienen tema.

  python3 herramientas/clasificar.py preparar [--tam 300]   # verificacion/temas/entrada-NN.json
  python3 herramientas/clasificar.py unir                   # salida-NN.json -> verificacion/temas.json

Las preguntas verificadas traen su tema del registro de verificación; este paso es para el resto.
"""
import glob, json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
CARPETA = os.path.join(RAIZ, 'verificacion', 'temas')
DESTINO = os.path.join(RAIZ, 'verificacion', 'temas.json')
TEMAS = {t['id'] for t in json.load(open(os.path.join(RAIZ, 'temas.json'), encoding='utf8'))}


def preparar(tam):
    cfg = json.load(open(os.path.join(RAIZ, 'bancos.json'), encoding='utf8'))
    hechos = json.load(open(DESTINO, encoding='utf8')) if os.path.exists(DESTINO) else {}
    pend = []
    completo = os.path.join(AQUI, '.cache', 'completo')   # todos los bancos, aunque la app muestre solo verificadas
    for b in cfg['bancos']:
        for q in json.load(open(os.path.join(completo, b['id'] + '.json'), encoding='utf8'))['preguntas']:
            clave = f"{b['id']}:{q['id']}"
            if not q.get('tema') and clave not in hechos:
                pend.append({'clave': clave, 'pregunta': q['stem'][:300],
                             'opciones': ' / '.join(q['opts'])[:250]})
    os.makedirs(CARPETA, exist_ok=True)
    for f in glob.glob(os.path.join(CARPETA, 'entrada-*.json')):
        os.remove(f)
    for n, i in enumerate(range(0, len(pend), tam), 1):
        json.dump(pend[i:i + tam], open(os.path.join(CARPETA, f'entrada-{n:02d}.json'), 'w', encoding='utf8'),
                  ensure_ascii=False, indent=0)
    print(f'{len(pend)} preguntas sin tema en {-(-len(pend) // tam)} archivos -> {CARPETA}')


def unir():
    hechos = json.load(open(DESTINO, encoding='utf8')) if os.path.exists(DESTINO) else {}
    for f in sorted(glob.glob(os.path.join(CARPETA, 'salida-*.json'))):
        d = json.load(open(f, encoding='utf8'))
        malos = {k: v for k, v in d.items() if v not in TEMAS}
        if malos:
            print(f'{os.path.basename(f)}: temas no válidos {list(malos.items())[:5]}')
        hechos.update({k: v for k, v in d.items() if v in TEMAS})
    json.dump(hechos, open(DESTINO, 'w', encoding='utf8'), ensure_ascii=False, indent=0, sort_keys=True)
    print(f'{len(hechos)} preguntas con tema en {DESTINO}')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == 'preparar':
        preparar(int(a[a.index('--tam') + 1]) if '--tam' in a else 300)
    elif a and a[0] == 'unir':
        unir()

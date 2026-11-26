"""Lotes por semana del cronograma, para los revisores (Sonnet).

  python3 herramientas/lotes_semana.py contar <semana>
      pendientes de esa semana en cada banco
  python3 herramientas/lotes_semana.py armar <banco> <semana> <prefijo> [--tam 15] [--max 60]
      escribe verificacion/escalar/<banco>/<prefijo>-01.json, -02 ... (listas de preguntas)
      ej.: armar lozano 5 w5   -> w5-01.json ... (sigue la numeración si ya existen)

Pendiente = sin registro en verificacion/<banco>.json ni en resultados/<banco>/, del sílabo,
y con tema de esa semana (temas.json). Alto valor (repetidas) primero.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rapido as R  # noqa: E402

V = R.V
BANCOS = ['pretest-2024', 'simulacros', 'banco-traducido', 'lozano']


def pendientes(banco, semana):
    preguntas, fuentes = R.cargar(banco)
    hechos = set(V.registros(banco)) | R.ids_en(os.path.join(R.VER, 'resultados', banco), '*.json')
    mapa = {t['id']: t.get('semana') for t in V._TEMAS}
    p = [q for q in preguntas if q['id'] not in hechos and '-' not in q['id'] and q['id'] in fuentes
         and q['tema'] not in V.FUERA_SILABO and semana in R.semanas(q['tema'], mapa)]
    p.sort(key=lambda q: not q.get('rep'))
    return p, fuentes


def armar(banco, semana, prefijo, tam=15, maximo=60):
    p, fuentes = pendientes(banco, semana)
    p = p[:maximo]
    carpeta = os.path.join(R.VER, 'escalar', banco)
    os.makedirs(carpeta, exist_ok=True)
    n = len(glob.glob(os.path.join(carpeta, f'{prefijo}-[0-9][0-9].json')))
    for i in range(0, len(p), tam):
        n += 1
        out = []
        for q in p[i:i + tam]:
            e = R.entrada_escalar(q, fuentes, R.texto_roto(q) or f'semana {semana}')
            e['tema'] = q['tema']
            out.append(e)
        ruta = os.path.join(carpeta, f'{prefijo}-{n:02d}.json')
        json.dump(out, open(ruta, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
        print(ruta, len(out))


if __name__ == '__main__':
    a = sys.argv[1:]

    def opcion(nom, defecto):
        return int(a[a.index(nom) + 1]) if nom in a else defecto

    if a[:1] == ['contar']:
        for b in BANCOS:
            print(b, len(pendientes(b, int(a[1]))[0]))
    elif a[:1] == ['armar']:
        armar(a[1], int(a[2]), a[3], opcion('--tam', 15), opcion('--max', 60))
    else:
        print(__doc__)

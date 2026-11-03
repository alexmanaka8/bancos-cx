#!/usr/bin/env python3
"""Buscador en los libros de cirugía (para verificar las claves de los bancos).

  python3 herramientas/libros.py indexar            # una vez, o cuando agregues un libro
  python3 herramientas/libros.py buscar "colecistitis alitiásica" [-n 8] [-l sabiston]
  python3 herramientas/libros.py pagina sabiston 1234 [1236-1238 ...]

El índice vive en herramientas/.cache/ y no se publica.
"""
import json, os, re, sqlite3, subprocess, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
GENERALES = os.path.dirname(os.path.dirname(AQUI))
CACHE = os.path.join(AQUI, '.cache', 'libros')
DB = os.path.join(CACHE, 'libros.db')

# id, nombre para citar, ruta (desde la carpeta GENERALES), forzar OCR
LIBROS = [
    ('sabiston', 'Sabiston. Tratado de cirugía, 21.ª ed.', 'Biblioteca /libros /Sabiston Tratado de cirugia 21era ed_260423_105708.pdf', False),
    ('gimenez', 'Giménez. Cirugía, 2.ª ed.', 'Biblioteca /libros /Gimenez 2da edicición - A color_260408_081635.pdf', True),
    ('absite', 'de Virgilio. Review of Surgery for ABSITE and Boards, 3.ª ed.', 'Biblioteca /libros /Cirugia  - ba_260518_191254.pdf', True),
    ('latarjet1', 'Latarjet. Anatomía humana, tomo 1', 'Biblioteca /libros /LaTarjet Tomo 1.pdf', False),
    ('latarjet2', 'Latarjet. Anatomía humana, tomo 2', 'Biblioteca /libros /LaTarjet Tomo 2.pdf', False),
    ('archundia', 'Archundia. Cirugía 1: educación quirúrgica', 'Primera semana de rotacion /2. Archundia - Técnica quirúgica.pdf', False),
    ('boros', 'Boros. Técnica quirúrgica', 'Primera semana de rotacion /2. Boros - Técnica quirúgica.pdf', False),
    ('mehu', 'MEHU. Técnica quirúrgica', 'Primera semana de rotacion /MEHU_TECNICA QUIRURGICA 260406_260519_232808.pdf', False),
]


def herramienta():
    binario = os.path.join(AQUI, '.bin', 'libros_texto')
    fuente = os.path.join(AQUI, 'libros_texto.swift')
    if not os.path.exists(binario) or os.path.getmtime(binario) < os.path.getmtime(fuente):
        os.makedirs(os.path.dirname(binario), exist_ok=True)
        subprocess.run(['swiftc', '-O', fuente, '-o', binario], check=True)
    return binario


def indexar():
    os.makedirs(CACHE, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("create virtual table if not exists pag using fts5(libro unindexed, p unindexed, t, tokenize='unicode61 remove_diacritics 2')")
    hechos = {r[0] for r in con.execute('select distinct libro from pag')}
    for lid, nombre, ruta, ocr in LIBROS:
        if lid in hechos:
            continue
        jsonl = os.path.join(CACHE, lid + '.jsonl')
        if not os.path.exists(jsonl):
            print('Leyendo', nombre, '(con OCR, tarda)…' if ocr else '…', flush=True)
            hechas = sum(1 for _ in open(jsonl + '.tmp', encoding='utf8')) if os.path.exists(jsonl + '.tmp') else 0
            while True:   # si se corta (memoria), sigue desde la última página guardada
                r = subprocess.run([herramienta()] + (['--ocr'] if ocr else []) + ['--desde', str(hechas + 1),
                                   os.path.join(GENERALES, ruta), jsonl + '.tmp'])
                ahora = sum(1 for _ in open(jsonl + '.tmp', encoding='utf8'))
                if r.returncode == 0 or ahora == hechas:
                    break
                hechas = ahora
            os.rename(jsonl + '.tmp', jsonl)
        with open(jsonl, encoding='utf8') as f:
            filas = [(lid, d['p'], d['t']) for d in map(json.loads, f)]
        con.executemany('insert into pag values (?,?,?)', filas)
        con.commit()
        print(f'  {nombre}: {len(filas)} páginas')


def nombre(lid):
    return next(n for i, n, _, _ in LIBROS if i == lid)


def buscar(q, n=8, libro=None):
    con = sqlite3.connect(DB)
    # palabras sueltas unidas con AND; "frase entre comillas" se respeta
    terminos = re.findall(r'"[^"]+"|\S+', q.replace('-', ' '))   # "Budd-Chiari" = "Budd Chiari"
    expr = ' '.join(t if t.startswith('"') else '"' + t.replace('"', '') + '"' for t in terminos)
    sql = "select libro, p, snippet(pag, 2, '«', '»', ' … ', 40) from pag where pag match ?"
    args = [expr]
    if libro:
        sql += ' and libro = ?'; args.append(libro)
    sql += ' order by rank limit ?'; args.append(n)
    filas = con.execute(sql, args).fetchall()
    if not filas and len(terminos) > 1:
        # ninguna página tiene todas las palabras: mostrar las que tienen más
        print('(Ninguna página tiene todas las palabras; resultados con algunas de ellas)\n')
        utiles = [t for t in re.findall(r'"[^"]+"', expr) if len(t) > 5]   # sin "de", "la", "en"…
        args[0] = ' OR '.join(utiles or re.findall(r'"[^"]+"', expr))
        filas = con.execute(sql, args).fetchall()
    if not filas:
        print('Sin resultados. Prueba sinónimos, menos palabras o el término en inglés (-l absite).')
    for lid, p, s in filas:
        print(f'[{lid} p.{p}] {nombre(lid)}\n   {" ".join(s.split())}\n')


def pagina(lid, ps):
    con = sqlite3.connect(DB)
    for p in ps:
        r = con.execute('select t from pag where libro=? and p=?', (lid, int(p))).fetchone()
        print(f'===== {nombre(lid)} · página {p} (del PDF) =====\n{r[0] if r else "(no existe)"}\n')


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == 'indexar':
        indexar()
    elif a[0] == 'buscar':
        n = int(a[a.index('-n') + 1]) if '-n' in a else 8
        l = a[a.index('-l') + 1] if '-l' in a else None
        buscar(a[1], n, l)
    elif a[0] == 'pagina':
        ps = []
        for x in a[2:]:   # acepta páginas sueltas y rangos: 1234 1236-1238
            i, _, f = x.partition('-')
            ps += range(int(i), int(f or i) + 1)
        pagina(a[1], ps)

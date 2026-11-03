"""Convierte las líneas extraídas de un PDF o foto en preguntas de opción múltiple.

Uso: python3 lineas_a_preguntas.py lineas.json salida.json

La respuesta correcta se toma, en este orden, de:
  1. "La respuesta correcta es: ..." (capturas del aula virtual)
  2. una sección "Respuestas" con líneas tipo "3. B. explicación"
  3. la opción resaltada en amarillo/verde
Si no hay ninguna (o hay varias opciones resaltadas), la pregunta queda "sin clave".
"""
import json, re, sys, unicodedata

OPT = re.compile(r'^\(?([a-fA-F])\s*[\.\)\-]\s*(?=\S)(.*)$')
NUM = re.compile(r'^(\d{1,3})\s*[\.\)\-]+\s*-?\s*(.*)$')
PREG = re.compile(r'^Pregunta\s+(\d{1,3})\b', re.I)
CLAVE_MOODLE = re.compile(r'^La respuesta correcta es:?\s*(.*)$', re.I)
RESP_TITULO = re.compile(r'^(Respuestas|RESPUESTAS|Clave de respuestas|CLAVE)\s*:?$')
RESP_LINEA = re.compile(r'^(\d{1,3})\s*[\.\)]\s*([A-Fa-f])\s*[\.\)]\s*(.*)$')
INICIO = re.compile(r'^(¿|Un |Una |El |La |Los |Las |Paciente|Mujer|Hombre|Var[oó]n|Niñ[oa]|Se |Cu[aá]l|Qu[eé] |En |Respecto|Con respecto|Sobre |Relacion|Indique|Señale|Marque|Todas |Es |Son |Durante |Tras |Despu[eé]s |Ante |Usted |Ud\.? |Lactante|Gestante|Adulto|Joven|Señor|Señora|Chico|Chica|Escolar|Recién)')
RADIO = re.compile(r'^[O0o○◯◉•®©]\s+(?=[a-eA-E]\s*[\.\)])')
LETRAS = 'abcdef'
MARCA = re.compile(r'\s+(X|x|v/|V|✓|✔|✗|✘|×)$')  # palomitas o aspas del OCR
RUIDO = re.compile(r'^(MAURICIO|CASTILLO|BANQUEO|Teammedic\.pe|Dr\. Mauricio|Castillo Gonzales|Mauricio|Castillo|'
                   r'Seleccione una:?|Machine Translated by Google|Incorrecta|Correcta|Parcialmente correcta|'
                   r'Punt[uú]a .*|P? ?Marcar pregunta|Finalizar revisi[oó]n|Mostrar todas las preguntas.*|'
                   r'Navegaci[oó]n por el cuestionario|Sin responder a[uú]n|\d{1,3}|[^\w¿?]{1,3})$', re.I)


# ---------- orden de lectura para OCR (corte XY recursivo) ----------
def _huecos(intervalos, minimo):
    cortes, fin = [], None
    for a, b in sorted(intervalos):
        if fin is not None and a - fin >= minimo:
            cortes.append((fin + a) / 2)
        fin = b if fin is None else max(fin, b)
    return cortes


def _partir(lines, cortes, eje):
    grupos, resto = [], lines
    for c in cortes:
        grupos.append([l for l in resto if eje(l) < c]); resto = [l for l in resto if eje(l) >= c]
    return grupos + [resto]


def ordenar_xy(lines, prof=0):
    if len(lines) <= 1 or prof > 12:
        return sorted(lines, key=lambda l: (l['y'], l['x']))
    x0 = min(l['x'] for l in lines); x1 = max(l['x'] + l['w'] for l in lines)
    v = [c for c in _huecos([(l['x'], l['x'] + l['w']) for l in lines], 12)
         if x0 + (x1 - x0) * 0.15 < c < x1 - (x1 - x0) * 0.1]
    if v:
        grupos = _partir(lines, v, lambda l: l['x'] + l['w'] / 2)
    else:
        h = _huecos([(l['y'], l['y'] + l['h']) for l in lines], 7)
        if not h:
            return sorted(lines, key=lambda l: (l['y'], l['x']))
        grupos = _partir(lines, h, lambda l: l['y'])
    return [l for g in grupos if g for l in ordenar_xy(g, prof + 1)]


def orden_lectura(lines):
    if not any(l.get('ocr') for l in lines):
        return lines
    out = []
    for p in sorted({l['p'] for l in lines}):
        out += ordenar_xy([l for l in lines if l['p'] == p])
    return out


# ---------- utilidades ----------
def opciones_en_linea(t):
    """'a. Plaquetas b. Macrófagos c. Fibroblastos' -> varias opciones."""
    m = OPT.match(t)
    if not m:
        return None
    partes = [(m.group(1).lower(), m.group(2))]
    while partes[-1][0] != 'f':
        sig = LETRAS[LETRAS.index(partes[-1][0]) + 1]
        mm = re.search(r'\s\(?' + sig + r'\s*[\.\)]\s+(?=\S)', partes[-1][1], re.I)
        if not mm:
            break
        txt = partes[-1][1]
        partes[-1] = (partes[-1][0], txt[:mm.start()])
        partes.append((sig, txt[mm.end():]))
    return partes


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower())
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in s if not unicodedata.combining(c)))


def es_seccion(t):
    """Encabezado de tema en MAYÚSCULAS (regla general, cuando el banco no define la suya)."""
    letras = [c for c in t if c.isalpha()]
    if len(letras) < 4 or len(t) > 70 or any(c.islower() for c in letras):
        return False
    if t[0] in '(\\[' or t.endswith((':', '.', ',')) or RUIDO.match(t) or OPT.match(t) or RESP_TITULO.match(t):
        return False
    return ' ' in t.strip() or len(letras) >= 7   # "PTFE", "EPOC" suelen ser siglas sueltas, no temas


def nombre_seccion(t):
    m = re.match(r'(?i)^semana\s*(\d+)\s*:?\s*tema\s*(\d+)', t)
    if m:
        return f'Semana {m.group(1)} · Tema {m.group(2)}'
    m = re.match(r'(?i)^semana\s*(\d+)', t)
    if m:
        return f'Semana {m.group(1)}'
    t = re.sub(r'^\d+\.\s*', '', t).strip(' .:-')
    return t[:1].upper() + t[1:].lower() if t.isupper() else t


def continua(prev, l):
    """¿La línea l sigue a prev dentro de la misma opción? Se decide por la posición en la página."""
    if prev is None or prev['p'] != l['p'] or prev.get('c') != l.get('c'):
        return False
    hueco = l['y'] - (prev['y'] + prev['h'])
    return -2 <= hueco <= max(prev['h'], 6) * 0.9 and l['x'] >= prev['x'] - 6


# ---------- análisis ----------
def parse(lines, temas=None):
    """temas: expresión regular opcional que reconoce los encabezados de tema de ese banco."""
    temas = re.compile(temas) if temas else None
    qs, sec = [], ''
    cur = None
    buffer = []          # líneas tras las opciones que aún no sabemos qué son
    prev_opt = None      # última línea que perteneció a una opción
    respuestas = {}      # número -> [letra, explicación] de la sección "Respuestas"
    modo_resp, resp_actual, visto_resp = False, None, False

    def cerrar():
        if cur and len(cur['opts']) >= 2:
            qs.append(cur)

    def nueva(texto, l, n=None):
        return {'stem': [texto] if texto else [], 'opts': [], 'p': l['p'], 'sec': sec, 'n': n, 'clave': None}

    def con_opciones(partes, hl):
        for le, tx in partes:
            if len(cur['opts']) < 6 and le == LETRAS[len(cur['opts'])]:
                cur['opts'].append({'t': [tx], 'hl': [hl]})

    for l in orden_lectura(lines):
        t = re.sub(r'\s+', ' ', l['t'].replace('￼', '')).strip()
        t = RADIO.sub('', t)
        if not t or RUIDO.match(t):
            continue
        hl = l.get('hl', 0)

        if RESP_TITULO.match(t):
            modo_resp = visto_resp = True; continue
        if visto_resp and RESP_LINEA.match(t):
            modo_resp = True
        if modo_resp:
            m = RESP_LINEA.match(t)
            if m:
                resp_actual = int(m.group(1))
                respuestas[resp_actual] = [m.group(2).lower(), m.group(3)]
                continue
            if NUM.match(t) or OPT.match(t):
                modo_resp, resp_actual = False, None   # volvió a haber preguntas
            else:
                if resp_actual:
                    respuestas[resp_actual][1] += ' ' + t
                continue

        if temas and temas.match(t):
            cerrar(); cur = None; buffer = []; prev_opt = None
            sec = nombre_seccion(t); continue

        m = CLAVE_MOODLE.match(t)
        if m and cur:
            cur['clave'] = m.group(1); continue

        m = PREG.match(t)
        if m:
            cerrar(); cur = nueva('', l, int(m.group(1))); buffer = []; prev_opt = None; continue

        partes = opciones_en_linea(t)
        if partes:
            letra = partes[0][0]
            if cur is not None and len(cur['opts']) < 6 and letra == LETRAS[len(cur['opts'])]:
                con_opciones(partes, hl); buffer = []; prev_opt = l; continue
            if letra == 'a':
                cerrar()
                cur = nueva(' '.join(x['t'] for x in buffer), l)
                con_opciones(partes, hl); buffer = []; prev_opt = l; continue
            # letra fuera de orden: se trata como texto normal

        m = NUM.match(t)
        if m and (cur is None or cur['opts']):
            cerrar(); cur = nueva(m.group(2), l, int(m.group(1))); buffer = []; prev_opt = None; continue
        if not temas and es_seccion(t) and (cur is None or cur['opts']):
            cerrar(); cur = None; buffer = []; prev_opt = None
            sec = nombre_seccion(t); continue
        if cur is None:
            cur = nueva(t, l); continue
        if not cur['opts']:
            if m and cur['n'] is None:   # el texto previo era encabezado: empieza aquí
                cur = nueva(m.group(2), l, int(m.group(1))); continue
            cur['stem'].append(t); continue

        # Ya hay opciones: ¿continuación de la última, inicio de otra pregunta o texto suelto?
        if not buffer and continua(prev_opt, l) and not INICIO.match(t):
            cur['opts'][-1]['t'].append(t); cur['opts'][-1]['hl'].append(hl); prev_opt = l; continue
        if INICIO.match(t) and len(cur['opts']) >= 2:
            cerrar(); cur = nueva(t, l); buffer = []; prev_opt = None; continue
        buffer.append({'t': t, 'p': l['p']})
    cerrar()

    # ---------- limpieza y clave ----------
    out, vistos = [], set()
    for q in qs:
        stem = ' '.join(q['stem']).strip(' -')
        stem = re.sub(r'^\d{1,3}\s*[\.\)\-]+\s*-?\s*', '', stem)
        stem = re.sub(r'\s*(Navegaci[oó]n por el cuestionario|Marcar pregunta|Seleccione una:?)\s*', ' ', stem).strip()
        opts = [MARCA.sub('', ' '.join(o['t'])).strip() for o in q['opts']]
        if len(stem) < 8 or any(not o for o in opts):
            continue
        key = norm(stem) + '|' + '|'.join(norm(o) for o in opts)
        if key in vistos:
            continue
        vistos.add(key)
        ans, por_que, fuente = None, '', ''
        if q['clave']:
            c = norm(q['clave'])
            cand = [i for i, o in enumerate(opts)
                    if norm(o) and (norm(o) == c or c.startswith(norm(o)) or norm(o).startswith(c))]
            if len(cand) == 1:
                ans, fuente = cand[0], 'aula virtual'
        if ans is None and q['n'] in respuestas:
            le, exp = respuestas[q['n']]
            if LETRAS.index(le) < len(opts):
                ans, por_que, fuente = LETRAS.index(le), exp.strip(), 'respuestas del documento'
        if ans is None:
            score = [max(o['hl']) for o in q['opts']]
            marcadas = [i for i, s in enumerate(score) if s >= 0.25]
            if len(marcadas) == 1:
                ans, fuente = marcadas[0], 'resaltado'
        item = {'stem': stem, 'opts': opts, 'ans': ans, 'p': q['p']}
        if q['sec']:
            item['sec'] = q['sec']
        if por_que:
            item['why'] = por_que
        if fuente:
            item['src'] = fuente
        out.append(item)
    return out


if __name__ == '__main__':
    data = json.load(open(sys.argv[1], encoding='utf8'))
    qs = parse(data['lines'])
    for i, q in enumerate(qs, 1):
        q['id'] = str(i)
    json.dump(qs, open(sys.argv[2], 'w', encoding='utf8'), ensure_ascii=False)
    con = sum(q['ans'] is not None for q in qs)
    print(f'{len(qs)} preguntas, {con} con clave')

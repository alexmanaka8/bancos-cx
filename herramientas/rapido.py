#!/usr/bin/env python3
"""Verificación rápida: poca IA, mucha mecánica (ver verificacion/RAPIDO.md).

  python3 herramientas/rapido.py preparar <banco> [--semana N] [--tam 15] [--max 60]
      junta evidencia de los libros y arma paquetes en verificacion/paquetes/<banco>/rNNN.json
  python3 herramientas/rapido.py piloto <banco> [--n 30] [--tam 15]
      igual, pero con preguntas ya verificadas (para medir) -> verificacion/paquetes/_piloto-<banco>/
  python3 herramientas/rapido.py comprobar <banco> <rNNN> [--estricto]
      lee rNNN.respuesta.json (del modelo barato), comprueba las citas en el libro y
      acepta (resultados/) o escala (escalar/). Con _piloto-<banco> solo compara con el "oro".
"""
import difflib, glob, json, math, os, random, re, sqlite3, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import verificar as V   # noqa: E402
import libros as L      # noqa: E402

VER = V.VER
PAQ = os.path.join(VER, 'paquetes')
NOMBRES = {
    'sabiston': 'Sabiston 21.ª ed.',
    'gimenez': 'Giménez, Cirugía 2.ª ed.',
    'absite': 'de Virgilio, Review of Surgery for ABSITE 3.ª ed.',
    'latarjet1': 'Latarjet, Anatomía humana, t. 1',
    'latarjet2': 'Latarjet, Anatomía humana, t. 2',
    'archundia': 'Archundia, Cirugía 1',
    'boros': 'Boros, Técnica quirúrgica',
    'mehu': 'MEHU, Técnica quirúrgica',
}
VENTANA = 1800      # caracteres de texto por página
TOPE = 6000         # caracteres de evidencia por pregunta
MAX_PAGINAS = 4
TECNICA = {'tecnica', 'suturas', 'seguridad', 'procedimientos', 'laparoscopia', 'historia'}

# ---------------------------------------------------------------- texto y términos
VACIAS = set("""
a al algo algun alguna algunas alguno algunos ante antes aquel aqui asi aun aunque bajo cada casi como con contra
cual cuales cuando cuanto de del desde donde dos durante e el ella ellas ello ellos en entre era eran es esa esas
ese eso esos esta estaba estan estar este esto estos fue fueron ha han hasta hay la las le les lo los mas me mi mis
mucho muy ni no nos nosotros o os otra otras otro otros para pero poco por porque que quien quienes se sea sean segun
ser si sido sin sobre solo su sus tambien tanto te tiene tienen todo todos tras tu tus un una unas uno unos y ya
siguiente siguientes cual cuales correcta correcto incorrecta incorrecto verdadero verdadera falso falsa excepto salvo
todas anteriores anterior ninguna ninguno alternativa alternativas marque senale indique respecto acerca opcion
afirmacion afirmaciones enunciado enunciados siguientes seria puede pueden debe deben considera considere cuales
paciente pacientes anos ano dias dia caso presenta presento refiere acude
a about above after again all also am an and any are as at be because been before being below between both but by
can could did do does doing down during each few for from further had has have having he her here hers him his how
i if in into is it its just may me might more most must my no nor not of off on once only or other our out over own
same she should so some such than that the their them then there these they this those through to too under until
up very was we were what when where which while who whom why will with would you your
""".split())
RAROS_CORTOS = {'iso', 'tnm', 'tep', 'ta', 'tc', 'rm', 'ecg', 'eco', 'tac', 'vih', 'epoc', 'ppi', 'ebv', 'hbv',
                'hcv', 'dvt', 'ards', 'aine', 'ain', 'eii', 'ca', 'tvp', 'tep', 'pvc', 'dm', 'hta', 'cea', 'afp',
                'psa', 'bmi', 'imc', 'ph', 'pcr', 'tsh', 'ctp', 'meld', 'ivu', 'itu', 'hbp', 'fev', 'ct', 'mri'}


def sin_acentos(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def limpiar(t):
    """Texto de página listo para leer/citar: une palabras cortadas por guion y colapsa espacios."""
    t = t.replace('­', '')
    t = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', t)
    return ' '.join(t.split())


def norm(t):
    """Normalización para comparar citas: minúsculas, sin acentos, sin signos, espacios colapsados."""
    t = sin_acentos(limpiar(t).lower())
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', t).split())


def palabras(t):
    return re.findall(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+', t)


def raiz(w):
    n = len(w)
    if w.isdigit():
        return w
    if n >= 7:
        return w[:max(5, n - 2)]
    if n >= 5:
        return w[:n - 1]
    return w


def terminos(texto):
    """Palabras clave (ya sin acentos, en minúscula) de un texto, sin repetir y en orden de aparición."""
    out, vistos = [], set()
    for w in palabras(texto):
        n = sin_acentos(w.lower())
        siglas = w.isupper() and 2 <= len(w) <= 5 and not w.isdigit()
        if n in VACIAS and not siglas:
            continue
        if w.isdigit():
            if len(w) < 2:
                continue
        elif len(n) < 4 and not (siglas or n in RAROS_CORTOS):
            continue
        r = raiz(n)
        if r not in vistos:
            vistos.add(r)
            out.append(r)
    return out


def clave_fon(w):
    """Clave para emparejar cognados español-inglés (apendicitis ~ appendicitis, aneurisma ~ aneurysm)."""
    w = sin_acentos(w.lower())
    w = re.sub(r'[^a-z0-9]', '', w).replace('ph', 'f').replace('th', 't').replace('y', 'i').replace('ck', 'k')
    return re.sub(r'(.)\1+', r'\1', w)


def clave_raiz(r):
    k = clave_fon(r)
    return k[:5] if len(k) >= 5 else k


# Glosario mínimo español -> inglés (raíz española : raíces inglesas), solo para emparejar con ABSITE, que está
# en inglés. Los cognados (apendicitis ~ appendicitis) ya se emparejan sin esto.
GLOSARIO = {
    'hece': ['feces', 'fecal', 'stool'], 'higad': ['liver', 'hepat'], 'rinon': ['kidney', 'renal'], 'renal': ['renal', 'kidney'],
    'pulmon': ['lung', 'pulmonary'], 'corazon': ['heart', 'cardiac'], 'estomag': ['stomach', 'gastric'],
    'intestin': ['bowel', 'intestin'], 'delgad': ['small'], 'grueso': ['large'], 'vesicul': ['gallbladder', 'cholecyst'],
    'biliar': ['biliary', 'bile'], 'bilis': ['bile'], 'bazo': ['spleen', 'splenic'], 'mama': ['breast'],
    'cuello': ['neck'], 'torax': ['chest', 'thorac'], 'dolor': ['pain'], 'fiebre': ['fever'], 'sangr': ['bleed', 'hemorrhag'],
    'sangre': ['blood'], 'hemorrag': ['bleed', 'hemorrhag'], 'vomit': ['vomit', 'emesis'], 'estrenim': ['constipation'],
    'distensi': ['distention', 'distended'], 'ictericia': ['jaundice', 'icter'], 'herida': ['wound'],
    'cicatriz': ['scar'], 'quemadur': ['burn'], 'hueso': ['bone'], 'musculo': ['muscle'], 'piel': ['skin', 'cutaneous'],
    'nervio': ['nerve'], 'vena': ['vein', 'venous'], 'arteria': ['artery', 'arterial'], 'arter': ['artery', 'arterial'],
    'ligadu': ['ligation', 'ligate'], 'absces': ['abscess'], 'infecci': ['infect'], 'tumor': ['tumor', 'mass'],
    'cancer': ['cancer', 'carcinoma'], 'quimioter': ['chemotherapy'], 'radiot': ['radiation', 'radiotherapy'],
    'irradi': ['radiation', 'irradiat'], 'ancian': ['elderly'], 'hombre': ['man', 'male'], 'mujer': ['woman', 'female'],
    'nino': ['child', 'pediatric'], 'embaraz': ['pregnan'], 'tratamiento': ['treatment', 'management'],
    'cirugia': ['surgery', 'surgical', 'operat'], 'resecc': ['resection'], 'extirp': ['resection', 'excision'],
    'choque': ['shock'], 'presion': ['pressure'], 'hipotens': ['hypotens'], 'hipertens': ['hypertens'],
    'antibiot': ['antibiotic'], 'fluido': ['fluid'], 'liquido': ['fluid'], 'sodio': ['sodium'], 'potasio': ['potassium'],
    'insuficiencia': ['failure', 'insufficiency'], 'obstrucci': ['obstruct'], 'perfor': ['perforat'],
    'inestable': ['unstable'], 'estable': ['stable'], 'semanas': ['weeks'], 'fuga': ['leak'],
    'neumotor': ['pneumothorax'], 'costill': ['rib'], 'contus': ['contusion', 'blunt'], 'cerrad': ['blunt'],
    'penetrante': ['penetrating'], 'ciego': ['cecum', 'cecal'], 'ulcera': ['ulcer'], 'sonda': ['tube', 'catheter'],
    'drenaje': ['drain'], 'diagnostic': ['diagnos'], 'mejor': ['best'], 'suprarren': ['suprarenal', 'adrenal'],
}


def en_claves(r):
    for k, v in GLOSARIO.items():
        if r.startswith(k) or (len(r) >= 4 and k.startswith(r)):
            return v
    return []


def prep_ingles(txt):
    """Índices de una página en inglés: claves fonéticas completas, de 5 letras, y prefijos de sus palabras."""
    ws = {sin_acentos(w.lower()) for w in palabras(txt)}
    kf = {clave_fon(w) for w in ws}
    pref = {w[:i] for w in ws for i in range(3, len(w) + 1)}
    return kf, {k[:5] for k in kf}, pref


def esta_en(r, pre):
    kf, k5, pref = pre
    c = clave_raiz(r)
    return (c in k5 if len(c) >= 5 else c in kf) or any(e in pref for e in en_claves(r))


def presentes_cognados(pre, util):
    return {r for r in util if esta_en(r, pre)}


# ---------------------------------------------------------------- acceso a los libros
class Libros:
    def __init__(self):
        self.con = sqlite3.connect(L.DB)
        self.n = self.con.execute('select count(*) from pag').fetchone()[0]
        self._df = {}
        self._pag = {}

    def df(self, r):
        if r not in self._df:
            self._df[r] = self.con.execute('select count(*) from pag where pag match ?', (self.q1(r),)).fetchone()[0]
        return self._df[r]

    @staticmethod
    def q1(r):
        return f'"{r}"' if r.isdigit() else f'"{r}"*'

    def idf(self, r):
        return math.log((self.n + 1) / (self.df(r) + 1))

    def pagina(self, libro, p):
        k = (libro, p)
        if k not in self._pag:
            f = self.con.execute('select t from pag where libro=? and p=?', (libro, int(p))).fetchone()
            self._pag[k] = limpiar(f[0]) if f else None
        return self._pag[k]

    def todas(self, libro):
        if libro not in self._pag:
            self._pag[libro] = [(p, limpiar(t)) for p, t in self.con.execute('select p, t from pag where libro=?', (libro,))]
        return self._pag[libro]

    def ingles(self, p, txt):
        if ('pre', p) not in self._pag:
            self._pag[('pre', p)] = prep_ingles(txt)
        return self._pag[('pre', p)]

    def buscar(self, expr, limite):
        try:
            return self.con.execute('select libro, p from pag where pag match ? order by rank limit ?',
                                    (expr, limite)).fetchall()
        except sqlite3.OperationalError:
            return []


def factor_libro(libro, tema):
    base = {'sabiston': 1.15, 'gimenez': 1.08, 'absite': 1.0}.get(libro)
    if base:
        return base
    if libro in ('archundia', 'boros', 'mehu'):
        return 1.12 if tema in TECNICA else 0.8
    if libro.startswith('latarjet'):
        return 1.0 if tema in ('hernias', 'anorrectal', 'trauma', 'higado', 'via-biliar') else 0.85
    return 0.8


def _or(rs):
    return ' OR '.join(Libros.q1(r) for r in rs)


def evidencia(lib, stem, opts, tema):
    ts = terminos(stem)
    to = [terminos(o) for o in opts]
    todos = list(dict.fromkeys(ts + [r for x in to for r in x]))
    peso = {r: lib.idf(r) ** 2 for r in todos}
    # fuera lo demasiado común (aparece en más del 25 % de las páginas) o ausente de todos los libros
    util = [r for r in todos if 0.25 * lib.n > lib.df(r) > 0]
    util.sort(key=lambda r: -peso[r])
    if not util:
        return []
    cand = set()
    top = util[:12]
    cand.update(lib.buscar(_or(top), 30))
    cand.update(lib.buscar(_or([r for r in ts if r in util][:8] or top[:6]), 20))
    if len(top) >= 3:
        cand.update(lib.buscar(' AND '.join(Libros.q1(r) for r in top[:3]), 15))
    base = [r for r in sorted((r for r in ts if r in util), key=lambda r: -peso[r])][:3]
    for x in to:
        xs = [r for r in x if r in util]
        if xs:
            cand.update(lib.buscar(_or(list(dict.fromkeys(base + xs[:5]))), 10))
    if len(top) >= 2:
        cand.update(lib.buscar(' AND '.join(Libros.q1(r) for r in top[:2]), 15))
    puntaje = []
    for libro, p in cand:
        if libro == 'absite':
            continue
        txt = lib.pagina(libro, p)
        if not txt:
            continue
        n = ' ' + norm(txt)
        tot = sum(peso[r] for r in util if ' ' + r in n)
        puntaje.append((tot * factor_libro(libro, tema), libro, p))
    # ABSITE está en inglés: se compara por cognados contra todas sus páginas (son pocas)
    for p, txt in lib.todas('absite'):
        tot = sum(peso[r] for r in presentes_cognados(lib.ingles(p, txt), util))
        puntaje.append((tot * factor_libro('absite', tema), 'absite', p))
    puntaje.sort(reverse=True)
    if not puntaje:
        return []
    mejor = puntaje[0][0]
    # a lo más 2 páginas por libro en la primera vuelta (diversidad); luego se rellena con las mejores
    validas = [x for x in puntaje if x[0] >= 0.5 * mejor]
    elegidas, por_libro = [], {}
    for x in validas:
        if por_libro.get(x[1], 0) < 2 and len(elegidas) < MAX_PAGINAS:
            elegidas.append(x)
            por_libro[x[1]] = por_libro.get(x[1], 0) + 1
    for x in validas:
        if x not in elegidas and len(elegidas) < MAX_PAGINAS:
            elegidas.append(x)
    out, usado = [], 0
    for _, libro, p in elegidas:
        resto = TOPE - usado
        if resto < 500:
            break
        txt = recorte(lib.pagina(libro, p), util, peso, min(VENTANA, resto), libro == 'absite')
        out.append({'libro': libro, 'nombre': NOMBRES.get(libro, libro), 'pagina': p, 'texto': txt})
        usado += len(txt)
    return out


def recorte(txt, util, peso, largo, ingles=False):
    """Ventana de ~largo caracteres (sin cortar palabras) con más términos distintos de la pregunta."""
    if len(txt) <= largo:
        return txt
    pal = [(m.start(), m.end(), sin_acentos(m.group().lower())) for m in re.finditer(r'\S+', txt)]
    marca = []
    for _, _, w in pal:
        if ingles:
            w0 = sin_acentos(w.lower())
            w0 = re.sub(r'[^a-z0-9]', '', w0)
            kw = clave_fon(w0)
            marca.append(next((r for r in util if (kw[:5] == clave_raiz(r) if len(clave_raiz(r)) >= 5 else kw == clave_raiz(r))
                               or any(w0.startswith(e) for e in en_claves(r))), None))
        else:
            w = re.sub(r'[^a-z0-9]', '', w)
            marca.append(next((r for r in util if w.startswith(r)), None))
    mejor, ini_mejor = -1, 0
    for i in range(0, len(pal), 4):
        ini = pal[i][0]
        j = i
        while j < len(pal) and pal[j][1] - ini <= largo:
            j += 1
        s = sum(peso[r] for r in {m for m in marca[i:j] if m})
        if s > mejor:
            mejor, ini_mejor, fin_mejor = s, i, j
    return txt[pal[ini_mejor][0]:pal[fin_mejor - 1][1]]


# ---------------------------------------------------------------- selección de preguntas
def texto_roto(q):
    o = q.get('opts') or []
    if q.get('ans') is None:
        return 'sin clave original'
    if len(o) < 3:
        return 'menos de 3 opciones'
    if len((q.get('stem') or '').strip()) < 15:
        return 'enunciado de menos de 15 caracteres'
    if any(not isinstance(x, str) or not x.strip() for x in o):
        return 'opciones vacías'
    return None


def semanas(tema_id, mapa):
    s = mapa.get(tema_id)
    return set() if s is None else set(s) if isinstance(s, list) else {s}


def cargar(banco):
    preguntas, fuentes = V._datos(banco)
    temas_k = {}
    ruta = os.path.join(VER, 'temas.json')
    if os.path.exists(ruta):
        temas_k = json.load(open(ruta, encoding='utf8'))
    for q in preguntas:
        q['tema'] = q.get('tema') or temas_k.get(f'{banco}:{q["id"]}') or 'otros'
    return preguntas, fuentes


def ids_en(carpeta, patron):
    ks = set()
    for f in glob.glob(os.path.join(carpeta, patron)):
        d = json.load(open(f, encoding='utf8'))
        if isinstance(d, dict) and 'preguntas' in d:
            d = d['preguntas']
        if isinstance(d, dict):
            ks |= set(d)
        else:
            ks |= {x['k'] for x in d if isinstance(x, dict) and 'k' in x}
    return ks


def siguiente_numero(banco):
    n = 0
    for carpeta in (os.path.join(PAQ, banco), os.path.join(VER, 'resultados', banco), os.path.join(VER, 'escalar', banco)):
        for f in glob.glob(os.path.join(carpeta, 'r[0-9][0-9][0-9]*.json')):
            n = max(n, int(os.path.basename(f)[1:4]))
    return n + 1


def paquete_de(lib, banco, num, lote, claves):
    pq = {'banco': banco, 'paquete': f'r{num:03d}', 'preguntas': []}
    for q in lote:
        pq['preguntas'].append({'k': q['id'], 'stem': q['stem'], 'opts': q['opts'], 'tema': q['tema'],
                                'evidencia': evidencia(lib, q['stem'], q['opts'], q['tema'])})
    return pq


def escribir_paquetes(lib, banco, carpeta, banco_real, preguntas, tam, num0=1, extra=None):
    os.makedirs(carpeta, exist_ok=True)
    total = 0
    for i in range(0, len(preguntas), tam):
        lote = preguntas[i:i + tam]
        num = num0 + i // tam
        pq = paquete_de(lib, banco_real, num, lote, None)
        nom = f'r{num:03d}'
        json.dump(pq, open(os.path.join(carpeta, nom + '.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
        json.dump({q['id']: q['ans'] for q in lote}, open(os.path.join(carpeta, nom + '.claves.json'), 'w', encoding='utf8'),
                  ensure_ascii=False, indent=1)
        if extra:
            json.dump({q['id']: extra[q['id']] for q in lote}, open(os.path.join(carpeta, nom + '.oro.json'), 'w', encoding='utf8'),
                      ensure_ascii=False, indent=1)
        total += len(json.dumps(pq, ensure_ascii=False))
    return total


def entrada_escalar(q, fuentes, motivo, pista=None):
    arch = fuentes.get(q['id']) or [None, None]
    e = {'k': q['id'], 'sec': q.get('sec'), 'stem': q['stem'], 'opts': q['opts'], 'clave_original': q.get('ans'),
         'origen_clave': q.get('src'), 'archivo': arch[0], 'pagina': arch[1], 'motivo': motivo}
    if pista:
        e['pista_modelo_barato'] = pista
    return e


def guardar_escalar(banco, nombre, entradas):
    if not entradas:
        return
    carpeta = os.path.join(VER, 'escalar', banco)
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre + '.json')
    lote = {'banco': banco, 'cubre_hasta': 'SOLO estas preguntas (lote filtrado): no busques preguntas perdidas',
            'nota': 'Escaladas por verificar.py rapido: el modelo barato no pudo comprobar la clave; sigue REGLAS.md. '
                    '"pista_modelo_barato" es solo una pista, no una fuente.',
            'preguntas': entradas}
    if os.path.exists(ruta) and nombre == 'previas':
        viejo = json.load(open(ruta, encoding='utf8'))['preguntas']
        hay = {x['k'] for x in entradas}
        lote['preguntas'] = [x for x in viejo if x['k'] not in hay] + entradas
    json.dump(lote, open(ruta, 'w', encoding='utf8'), ensure_ascii=False, indent=1)


def preparar(banco, semana=None, tam=15, maximo=60):
    preguntas, fuentes = cargar(banco)
    hechos = set(V.registros(banco)) | ids_en(os.path.join(VER, 'resultados', banco), '*.json')
    hechos |= ids_en(os.path.join(VER, 'escalar', banco), '*.json') | ids_en(os.path.join(PAQ, banco), 'r*.claves.json')
    mapa = {t['id']: t.get('semana') for t in V._TEMAS}
    pend = [q for q in preguntas if q['id'] not in hechos and '-' not in q['id'] and q['id'] in fuentes
            and q['tema'] not in V.FUERA_SILABO]
    if semana is not None:
        pend = [q for q in pend if semana in semanas(q['tema'], mapa)]
    pend.sort(key=lambda q: not q.get('rep'))   # alto valor primero (orden estable)
    rotas = [(q, texto_roto(q)) for q in pend]
    buenas = [q for q, m in rotas if not m][:maximo]
    guardar_escalar(banco, 'previas', [entrada_escalar(q, fuentes, m) for q, m in rotas if m])
    lib = Libros()
    num = siguiente_numero(banco)
    carpeta = os.path.join(PAQ, banco)
    chars = escribir_paquetes(lib, banco, carpeta, banco, buenas, tam, num)
    npaq = -(-len(buenas) // tam)
    print(f'{banco}: {len(pend)} pendientes del sílabo; {sum(1 for _, m in rotas if m)} apartadas sin IA (escalar/{banco}/previas.json); '
          f'{len(buenas)} preguntas en {npaq} paquetes ({chars:,} caracteres en total, ~{chars // max(npaq, 1):,} por paquete) -> {carpeta}')


def piloto(banco, n=30, tam=15):
    preguntas, fuentes = cargar(banco)
    regs = V.registros(banco)
    por_id = {q['id']: q for q in preguntas}
    elegibles = sorted(k for k, r in regs.items() if r['estado'] in ('confirmada', 'corregida')
                       and k in por_id and not texto_roto(por_id[k]))
    random.Random(2026).shuffle(elegibles)
    sel = [por_id[k] for k in elegibles[:n]]
    oro = {k: {'ans': regs[k]['ans'], 'estado': regs[k]['estado'], 'fuentes': regs[k].get('fuentes', [])} for k in elegibles[:n]}
    carpeta = os.path.join(PAQ, '_piloto-' + banco)
    for f in glob.glob(os.path.join(carpeta, '*')):
        os.remove(f)
    lib = Libros()
    chars = escribir_paquetes(lib, banco, carpeta, banco, sel, tam, 1, oro)
    npaq = -(-len(sel) // tam)
    print(f'piloto {banco}: {len(sel)} preguntas en {npaq} paquetes ({chars:,} caracteres, ~{chars // max(npaq, 1):,} por paquete) -> {carpeta}')


# ---------------------------------------------------------------- comprobar la cita
def mejor_parecido(cita_n, pag_n):
    """Mejor razón difflib de cita_n contra ventanas de su mismo largo de pag_n."""
    m = len(cita_n)
    if cita_n in pag_n:
        return 1.0
    if len(pag_n) <= m:
        return difflib.SequenceMatcher(None, cita_n, pag_n, autojunk=False).ratio()
    paso = max(8, m // 16)
    mejor, donde = 0.0, 0
    for i in range(0, len(pag_n) - m + paso, paso):
        i = min(i, len(pag_n) - m)
        sm = difflib.SequenceMatcher(None, cita_n, pag_n[i:i + m], autojunk=False)
        if sm.real_quick_ratio() < 0.8 or sm.quick_ratio() < 0.8:
            continue
        r = sm.ratio()
        if r > mejor:
            mejor, donde = r, i
    if mejor >= 0.8:
        for i in range(max(0, donde - paso), min(len(pag_n) - m, donde + paso) + 1):
            r = difflib.SequenceMatcher(None, cita_n, pag_n[i:i + m], autojunk=False).ratio()
            mejor = max(mejor, r)
    return mejor


def comprobar_cita(lib, cita, otras):
    """(ok, libro, pagina, razon). Si no está en la página citada, la busca en las otras de la evidencia."""
    if not isinstance(cita, dict):
        return False, None, None, 'cita ausente o mal formada'
    libro, pag, texto = cita.get('libro'), cita.get('pagina'), cita.get('texto')
    if not isinstance(texto, str) or not isinstance(libro, str):
        return False, None, None, 'cita ausente o mal formada'
    try:
        pag = int(pag)
    except (TypeError, ValueError):
        return False, None, None, 'cita sin página válida'
    n = norm(texto)
    if len(texto.strip()) < 40 or len(n) < 30:
        return False, None, None, 'cita demasiado corta'
    if len(texto) > 600:
        return False, None, None, 'cita demasiado larga'
    best = 0.0
    for lb, pg in [(libro, pag)] + [x for x in otras if x != (libro, pag)]:
        t = lib.pagina(lb, pg)
        if not t:
            if (lb, pg) == (libro, pag):
                best = max(best, 0.0)
            continue
        r = mejor_parecido(n, norm(t))
        best = max(best, r)
        if r >= 0.90:
            return True, lb, pg, f'parecido {r:.2f}'
    return False, None, None, f'cita no encontrada en el libro (mejor parecido {best:.2f})'


def comprobar(nombre_banco, nombre, estricto=False):
    piloto_ = nombre_banco.startswith('_piloto-')
    banco = nombre_banco[len('_piloto-'):] if piloto_ else nombre_banco
    carpeta = os.path.join(PAQ, nombre_banco)
    pq = json.load(open(os.path.join(carpeta, nombre + '.json'), encoding='utf8'))
    claves = json.load(open(os.path.join(carpeta, nombre + '.claves.json'), encoding='utf8'))
    oro = json.load(open(os.path.join(carpeta, nombre + '.oro.json'), encoding='utf8')) if piloto_ else {}
    ruta_r = os.path.join(carpeta, nombre + '.respuesta.json')
    resp = json.load(open(ruta_r, encoding='utf8'))
    if isinstance(resp, dict):
        resp = resp.get('respuestas') or list(resp.values())
    por_k = {r['k']: r for r in resp if isinstance(r, dict) and 'k' in r}
    preguntas, fuentes = cargar(banco)
    por_id = {q['id']: q for q in preguntas}
    lib = Libros()
    ok, esc = [], []
    for p in pq['preguntas']:
        k = p['k']
        r = por_k.get(k)
        q = por_id.get(k) or {'id': k, 'stem': p['stem'], 'opts': p['opts'], 'ans': claves.get(k)}
        orig = claves.get(k)
        motivo = None
        if not isinstance(r, dict):
            motivo = 'sin respuesta del modelo barato'
        elif r.get('decide') is not True:
            motivo = 'el modelo barato no pudo decidir con la evidencia'
        elif not isinstance(r.get('ans'), int) or isinstance(r.get('ans'), bool) or not 0 <= r['ans'] < len(p['opts']):
            motivo = 'registro mal formado (ans)'
        if not motivo:
            otras = [(e['libro'], e['pagina']) for e in p['evidencia']]
            bien, lb, pg, det = comprobar_cita(lib, r.get('cita'), otras)
            if not bien:
                motivo = det
            elif r['ans'] != orig:
                motivo = f'la respuesta del modelo barato ({chr(65 + r["ans"])}) difiere de la clave original ({chr(65 + orig)})'
            elif estricto and not apoya(r['cita']['texto'], p['opts'][r['ans']]):
                motivo = 'la cita no menciona la opción elegida (modo estricto)'
        if motivo:
            pista = None
            if isinstance(r, dict):
                pista = {x: r.get(x) for x in ('decide', 'ans', 'cita', 'why', 'tema')}
            esc.append((q, motivo, pista, r))
            continue
        tema = r.get('tema') if r.get('tema') in V.TEMAS else p['tema']
        reg = {'k': k, 'estado': 'confirmada', 'stem': p['stem'], 'opts': p['opts'], 'ans': r['ans'],
               'why': (r.get('why') or '').strip(), 'fuentes': [f'{NOMBRES.get(lb, lb)}, p. {pg} del PDF'],
               'nota': 'Verificación rápida: cita comprobada en el libro.', 'tema': tema}
        err = V._errores_registro(reg, k)
        if err:
            esc.append((q, 'registro inválido: ' + '; '.join(err), {x: r.get(x) for x in ('decide', 'ans', 'cita', 'why', 'tema')}, r))
            continue
        ok.append(reg)
    resumen(nombre_banco, nombre, pq, ok, esc, oro, banco, fuentes, piloto_, claves)


def apoya(cita, opcion):
    c = ' ' + norm(cita)
    rs = terminos(opcion)
    return not rs or any(' ' + r in c for r in rs)


def resumen(nombre_banco, nombre, pq, ok, esc, oro, banco, fuentes, piloto_, claves):
    total = len(pq['preguntas'])
    if not piloto_:
        os.makedirs(os.path.join(VER, 'resultados', banco), exist_ok=True)
        rr = os.path.join(VER, 'resultados', banco, nombre + '.json')
        if ok:
            json.dump(ok, open(rr, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
            V.validar(rr)
        elif os.path.exists(rr):
            os.remove(rr)
        guardar_escalar(banco, nombre, [entrada_escalar(q, fuentes, m, pista) for q, m, pista, _ in esc])
    motivos = {}
    for _, m, _, _ in esc:
        m0 = re.sub(r'\(mejor parecido [\d.]+\)', '', m)
        m0 = re.sub(r'\(\w\) difiere de la clave original \(\w\)', 'difiere de la clave original', m0)
        motivos[m0] = motivos.get(m0, 0) + 1
    print(f'{nombre_banco} {nombre}: {total} preguntas; aceptadas {len(ok)}; a escalar {len(esc)}')
    for m, c in sorted(motivos.items(), key=lambda x: -x[1]):
        print(f'   escalar ({c}): {m}')
    if piloto_:
        malas = [(r['k'], r['ans'], oro[r['k']]['ans']) for r in ok if r['ans'] != oro[r['k']]['ans']]
        print(f'   aceptadas que coinciden con el oro: {len(ok) - len(malas)}/{len(ok)}')
        for k, a, o in malas:
            print(f'   DISCREPANCIA k={k}: rápida={chr(65 + a)} oro={chr(65 + o)}')
        print(f'   resueltas sin escalar: {100 * len(ok) / max(total, 1):.0f} %')
        for q, m, pista, r in esc:
            o = oro[q['id']]
            a = pista.get('ans') if pista else None
            print(f'   - escalada {q["id"]}: {m} | modelo={chr(65 + a) if isinstance(a, int) else None} clave={chr(65 + claves[q["id"]])} oro={chr(65 + o["ans"])} ({o["estado"]})')


if __name__ == '__main__':
    a = sys.argv[1:]

    def opcion(nom, defecto, tipo=int):
        return tipo(a[a.index(nom) + 1]) if nom in a else defecto
    if len(a) >= 2 and a[0] == 'preparar':
        preparar(a[1], opcion('--semana', None), opcion('--tam', 15), opcion('--max', 60))
    elif len(a) >= 2 and a[0] == 'piloto':
        piloto(a[1], opcion('--n', 30), opcion('--tam', 15))
    elif len(a) >= 3 and a[0] == 'comprobar':
        comprobar(a[1], a[2], '--estricto' in a)
    else:
        print(__doc__)

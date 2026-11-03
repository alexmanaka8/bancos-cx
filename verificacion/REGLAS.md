# Reglas para verificar las claves de los bancos

Objetivo: que cada pregunta tenga **la respuesta correcta según la evidencia**, con una explicación y su fuente. Los bancos los armaron estudiantes. Sus claves (resaltados, capturas del aula virtual) **no son confiables por sí solas**: pueden ser lo que un alumno marcó en el examen.

**Regla de oro: no inventar ni adivinar.** Si una fuente fiable no permite decidir, la pregunta queda `dudosa`. Nunca se elige "la más probable".

## Paso 1 · Texto de la pregunta
1. Compara el texto con la página original:
   ```
   python3 herramientas/verificar.py original <banco> <k>
   ```
   El comando imprime la ruta de la imagen. Ábrela con la herramienta Read.
2. **Repara el texto** cuando haga falta: palabras cortadas, opciones faltantes o pegadas, basura de la conversión, letras "a) b)" dentro del texto.
   - Corrige solo lo que **se ve en el original**. No completes de memoria.
   - Escribe `stem` sin el número de pregunta y `opts` sin la letra.
3. Si el ítem tiene **varias preguntas pegadas**, la primera queda en el registro y las demás van en `dividir` (ver el formato). Cada pregunta separada se verifica igual que las demás.
4. Si la pregunta está **incompleta en el propio original** (cortada en la foto, faltan opciones) y no se puede entender, el estado es `anulada`. Explica en `why` qué falta.

### Que no falte ninguna pregunta
La extracción automática a veces **pierde preguntas enteras**. Tu lote cubre todas las preguntas del original desde tu primer ítem hasta justo antes de la pregunta indicada en `cubre_hasta`. Si en esas páginas hay una pregunta que no está en tu lote (ni en ningún `dividir`), **agrégala** como un registro más con:
- `"agregada": true`
- `"k": "<lote>-a1"`, `"<lote>-a2"`…
- `"despues_de"`: el `k` de la pregunta que la precede en el original.
Se verifica igual que las demás.

## Paso 2 · Verificar la respuesta
Fuentes, en este orden de autoridad:
1. **Libros de la carpeta**, a través del buscador:
   ```
   python3 herramientas/libros.py buscar "términos clave" -n 8 [-l sabiston]
   python3 herramientas/libros.py pagina sabiston 1234 1235
   ```
   | Libro (`-l`) | Contenido |
   |---|---|
   | `sabiston` | Sabiston 21.ª ed. en español: la referencia principal de cirugía general |
   | `gimenez` | Giménez, Cirugía 2.ª ed. (autor argentino, muy usado en Latinoamérica) |
   | `absite` | de Virgilio, Review of Surgery for ABSITE (inglés, preguntas tipo board) |
   | `latarjet1`, `latarjet2` | Anatomía |
   | `archundia`, `boros`, `mehu` | Técnica quirúrgica, instrumental, asepsia, suturas |

   El buscador es por palabras (todas deben aparecer). Usa 2–4 términos, en español y también en inglés para `absite`, y prueba sinónimos. **Lee la página completa** con `pagina` antes de citarla: el fragmento solo no basta.
2. **Guías oficiales en la web**, solo cuando el tema es de guía y no de libro. Ejemplos: AHA/ERC (RCP, cardioversión), ATLS, Lista de verificación OMS, CDC/NHSN (heridas, infección del sitio operatorio), WHO, MINSA Perú, Tokyo Guidelines, WSES. También vale NCBI/StatPearls o PubMed.
   - **Prohibido usar como fuente:** Quizlet, Brainly, Scribd, blogs, foros, otros bancos de preguntas o resúmenes de estudiantes, y respuestas de IA.
   - Consejo: NCBI/PMC, StatPearls y ahajournals suelen bloquear WebFetch. La API de Europe PMC (`https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=...&format=json&resultType=core`) y `.../rest/PMCxxxx/fullTextXML` sí funcionan. Para un PDF oficial, descárgalo a tu scratchpad y léelo con un script de PDFKit.
3. **Si las fuentes se contradicen** (por ejemplo, una guía nueva frente al libro), vale la más reciente y oficial. Explica la diferencia en `nota`.

Criterio del examen frente al libro: **la clave es la que respalda la evidencia.** Si la clave original difiere y parece ser lo que el examen de la UPAO esperaba (por ejemplo, viene del aula virtual, que es la clave oficial), explícalo en `nota`. Ejemplo: "En el aula virtual la clave fue B; el Sabiston respalda C porque…".

Estados:
| Estado | Cuándo |
|---|---|
| `confirmada` | La fuente respalda la clave original. |
| `corregida` | La fuente respalda otra opción. `ans` es la correcta. |
| `nueva` | No tenía clave y la fuente permite decidirla. |
| `dudosa` | Ninguna fuente fiable decide, la pregunta es ambigua o hay dos opciones defendibles. `ans` = null. En `why` explica qué dice la evidencia y por qué no alcanza. |
| `anulada` | El texto está roto o incompleto en el original, o ninguna opción es correcta. `ans` = null. |

Para cuestiones de **historia, nombres o definiciones** (etimología, quién hizo la primera cirugía de X), también se exige fuente: un libro o una referencia histórica seria.

## Tema
Cada registro (también los de `dividir` y los agregados) lleva `"tema"`: el `id` de **un** tema de `temas.json` (los temas del sílabo de Cirugía I). Elige el más específico según lo que pregunta. Por ejemplo, "gérmenes de la ISO tras apendicectomía" va en `iso`, no en `apendicitis`. Si no encaja en ninguno, usa `otros`.

## Paso 3 · Explicación (`why`), en español
- 2 a 5 frases: **por qué la correcta es correcta**, con el dato clave del libro, y **por qué las otras no**, en una frase cada una o agrupadas.
- Clara y para estudiar, sin relleno.
- Si la explicación usa una cita textual, que sea breve y en comillas.

## Formato del resultado
Escribe `verificacion/resultados/<banco>/<lote>.json`: una lista con un registro por pregunta del lote, **en el mismo orden**.
```json
[
 {
  "k": "a1b2c3d4e5",
  "estado": "corregida",
  "stem": "Texto completo y reparado de la pregunta",
  "opts": ["Opción A", "Opción B", "Opción C", "Opción D"],
  "ans": 2,
  "why": "Explicación…",
  "fuentes": ["Sabiston 21.ª ed., p. 254 del PDF", "CDC/NHSN 2024, Surgical Site Infection Event (https://…)"],
  "nota": "Clave original: A (resaltado). …",
  "tema": "cicatrizacion",
  "dividir": [ { "estado": "…", "stem": "…", "opts": ["…"], "ans": 1, "why": "…", "fuentes": ["…"] } ]
 }
]
```
- `ans` es el índice empezando en 0 (A = 0, B = 1…). Comprueba que coincida con el texto de la opción que quieres marcar.
- `nota` y `dividir` son opcionales.
- En `fuentes` usa el formato "Libro, p. N del PDF", la página que da el buscador.
- Al terminar, valida el archivo y corrige hasta que diga OK:
  ```
  python3 herramientas/verificar.py validar <archivo>
  ```

No toques otros archivos del proyecto.

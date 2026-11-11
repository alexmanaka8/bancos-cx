# Rediseño de la app: lo que pidió quien la usa (2026-11-07)

Para hacerlo en una conversación nueva. Antes de empezar, leer la memoria del proyecto y `docs/` (index.html, banco.html, comun/app.css, comun/app.js).
Hay que responder siempre en español y con explicaciones simples.

## Falta un dato: el cronograma
- Hace falta el **cronograma del curso de Cirugía I**: qué temas van en cada semana.
- Quien usa la app lo va a adjuntar en la conversación nueva.
- Hoy `temas.json` solo tiene el número de clase del sílabo (campo `clase`), sin semanas.
- Hay que agregar un campo `semana` a cada tema según el cronograma; también puede ir en un `cronograma.json` aparte.

## Organización
1. **Por semanas.** Los temas se agrupan según el cronograma. Hoy están muy dispersos.
2. **Inicio claro.** Al entrar se elige:
   - practicar un tema específico, solo de ese tema;
   - practicar por semana, según el cronograma;
   - armar un examen personalizado.
3. **Examen personalizado.** Se eligen uno o varios temas, o una o varias semanas, y la cantidad de preguntas.
4. **Simulacro semanal.** 45 preguntas en 25 minutos, solo de los temas de la semana elegida. Tiene un temporizador general y la corrección se ve al final.

## Estadísticas y avance (sección propia)
- **Cronómetro por pregunta.** Se guarda el tiempo de cada respuesta. En estadísticas aparecen el tiempo promedio por pregunta y el tiempo total de simulación.
- **Proyección de avance.** Al ritmo actual (preguntas por día), cuántos días faltan para ver todo el banco.
- **Proyección de puntaje.** Nota estimada (sobre 20) según el porcentaje de aciertos reciente, idealmente ponderado por tema.
- **Precisión por especialidad o tema.** Un gráfico radial (spider chart) o de barras horizontales con el % de aciertos por área.
- **Top 3 temas críticos.** Se calcula solo: los temas con mayor índice de error, con un mínimo de preguntas respondidas.
- **Cobertura.** Una barra global con las preguntas vistas frente a las disponibles.
- **Estado del banco (embudo).** Un gráfico circular con cuatro partes:
  - preguntas nuevas (no vistas);
  - acertadas a la primera;
  - falladas;
  - marcadas o dudosas (guardadas para revisar, aunque estén acertadas).
- **Temas débiles.** Una vista que muestre en qué temas va mal.

## Interfaz
- **Textos encimados.** Corregir los textos que se sobreponen en la pantalla de elegir preguntas o filtros.
- **Más dinámica.** Menos genérica y aburrida.
- **Menú lateral.** Una barra de navegación al costado (en el celular, un menú tipo hamburguesa o una barra inferior). Las secciones son Inicio, Practicar, Simulacro, Estadísticas, Bancos y Biblioteca, para no tener todo amontonado en una sola página larga.
- **Lo que no puede cambiar:**
  - Sigue siendo PWA y funciona sin internet.
  - No se pierde el progreso guardado: localStorage, con las claves actuales `pwa:...`.
  - Se siguen mostrando solo las preguntas verificadas.
  - Las preguntas siguen teniendo su explicación y su fuente.

## Notas técnicas
- Los datos de cada pregunta ya traen `tema`, `rep` (alto valor) y `ver`.
- El progreso por banco se guarda en localStorage. Para el modo por tema ya existe un Proxy que reparte el progreso en los almacenes de cada banco.
- Para guardar el tiempo y el historial de intentos hay que añadir un registro de respuestas: id, fecha, tiempo, si acertó y si fue al primer intento.
- Después de cambiar algo: `python3 herramientas/construir.py`. Luego hay que probar en el navegador del panel (escritorio y celular) y avisar que se haga Commit + Push en GitHub Desktop.

## Estado (2026-11-07): HECHO
- Cronograma en `cronograma.json` (semanas, fechas, exámenes) y campo `semana` en `temas.json` (intestino = 4 y 5; trauma = 6 y 7).
- `index.html` = Inicio / Practicar (tema, semana, a medida) / Simulacro / Estadísticas / Bancos / Biblioteca, con menú lateral o barra inferior.
- `banco.html` acepta `?id=`, `?tema=`, `?temas=a,b`, `?semana=N`, `?semanas=1,3`, `?sim=N` (+ `n`, `f`, `auto=1`).
- Nuevas claves en localStorage: `pwa:registro` (cada respuesta: id, fecha, ms, acierto, primer intento) y `pwa:simulacros`. Sesiones: `pwa:semana-N`, `pwa:examen`, `pwa:simulacro-N`.

## Estado (repaso, meta, tema)
Hecho en `docs/comun/app.js`, `app.css`, `index.html`, `banco.html`, `biblioteca.html` (sin probar en navegador; falta revisión a mano).

**Claves nuevas de localStorage**
- `pwa:ajustes` = `{ meta: 30, tema: 'auto' | 'light' | 'dark', vibrar: true }`. Meta diaria (10, 20, 30, 45, 60), aspecto y vibración.
- `pwa:repaso` = sesión a medias del repaso de hoy (mismo formato que las otras sesiones). El calendario de repasos NO se guarda: se calcula de `pwa:registro` (y de `hist.last` en las preguntas viejas sin registro).

**Parámetros nuevos de URL**
- `banco.html?repaso=1`: repaso espaciado de hoy (máx. 30 por sesión, empieza directo).
- `index.html#practicar/repaso`: pestaña "Repaso".

**Reglas del repaso**: última respuesta mal → mañana; racha de aciertos 1 → 3 días, 2 → 7, 3 → 14, 4 o más → 30. "Dominadas" = racha 3 o más.

**Otros**: `data-theme` en `<html>` (script mínimo en el `<head>` de las tres páginas); gestos (izquierda = siguiente, derecha = anterior, ignora 24 px de cada borde); pantalla encendida (Wake Lock) durante el simulacro; mapa del simulacro plegado en celular y en columna derecha desde 900 px; atajos de teclado en computadora (A–E / 1–5, Enter, flechas, M).

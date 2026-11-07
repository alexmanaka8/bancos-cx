# Cómo seguir la verificación (para una conversación nueva)

Estado al 2026-11-06: 655 preguntas verificadas en la app.
- Bancos terminados: examenes-2026, fotos, final-2021, cicatrizacion, recopilacion-2021.
- Alto valor (⭐): 387 de 393 verificadas.
- Ver el detalle con `python3 herramientas/verificar.py estado`.

## Decisiones de quien usa la app (no volver a preguntar)
- **Solo temas del sílabo.** Generar los lotes con `--silabo`, que salta los temas "fuera del sílabo" y "otros".
- **Ahorrar uso.** El revisor NO abre la imagen del original salvo que el texto se vea roto, que falten opciones o que no haya clave original.
- **Orden de bancos:** pretest-2024 → simulacros → banco-traducido → lozano (Lozano ya tiene sus lotes hechos con `--silabo`, 43 lotes de 25).
- **Lotes por tanda:** 6 a 8 en paralelo, y luego parar para que quien usa la app publique (Commit + Push en GitHub Desktop).
- **Respuestas:** siempre en español, simple, para principiante.

## Pasos de cada tanda
1. `python3 herramientas/verificar.py lotes <banco> --tam 25 --silabo`. No hace falta para Lozano, que ya tiene los lotes.
2. Lanzar un revisor por lote (Agent, general-purpose, en segundo plano) con el texto de abajo.
3. Cuando terminen:
   - Correr `python3 herramientas/verificar.py unir <banco>`.
   - Buscar repetidas resueltas distinto: el mismo enunciado y las mismas opciones en dos bancos deben tener la misma clave. Si difieren, decidir con el libro.
   - Correr `python3 herramientas/construir.py`.
4. Revisar en los informes:
   - Los datos "de memoria": quitarlos.
   - Las confirmadas "por descarte" sin fuente directa: pasarlas a dudosas.
5. Avisar a quien usa la app que haga Commit + Push.

## Texto para cada revisor (cambiar BANCO y NNN)
```
Eres un revisor médico experto en cirugía general. Vas a verificar las claves de preguntas de examen de Cirugía I (UPAO, Perú) del banco de estudio de una persona que estudia medicina. La exactitud es lo más importante: una clave equivocada le enseña algo falso.

Carpeta: "/Users/alejandro/Material Cx1 /GENERALES /app-bancos" ("Material Cx1 " y "GENERALES " llevan un espacio al final: usa siempre comillas).

1. Lee y sigue verificacion/REGLAS.md, con UNA excepción para ahorrar: NO abras la imagen del original salvo que el texto de la pregunta se vea roto o cortado, que falten opciones o que la clave original venga vacía. En ese caso usa `python3 herramientas/verificar.py original BANCO <k>` y Read. Lee también temas.json.
2. Tu lote es verificacion/lotes/BANCO/NNN.json. Verifica SOLO esas preguntas; no busques preguntas perdidas.
3. Para cada pregunta:
   - Verifica con los libros: `python3 herramientas/libros.py buscar ...` y `pagina ...` (acepta rangos A-B). Llama a libros.py directamente, no lo guardes en una variable de shell.
   - Usa la web solo para guías oficiales o artículos revisados por pares (la API de Europe PMC funciona bien).
   - Si la evidencia no decide, la pregunta es "dudosa". Nunca adivines ni confirmes "por descarte" sin fuente.
   - En "why" y "nota" pon solo datos que hayas leído en una fuente citada; nada "de memoria".
   - Pon "tema" en cada registro.
4. Escribe verificacion/resultados/BANCO/NNN.json y valídalo con `python3 herramientas/verificar.py validar <archivo>` hasta que dé OK.
5. No modifiques otros archivos. Si usas el scratchpad, trabaja en una subcarpeta propia.

Al terminar responde con un resumen BREVE:
- El conteo por estado.
- Una línea por cada corregida, dudosa o anulada: la clave original, la tuya y la fuente.
```

## Pendientes conocidos
- Hay 3 preguntas de balance hídrico (recopilacion-2021 y examenes-2026) que necesitan la fórmula de pérdidas insensibles del curso. Ya se pidió.
- Una pregunta de quemado de 100 kg (recopilacion-2021, d44bfcc802): si el curso usa siempre Parkland, la clave es A (6000 ml).
- El banco HTML semana1 no está en el sistema de verificación. Sus preguntas idénticas a las de otros bancos se quedan en semana1 y no salen en la app.

# Verificación rápida (poca IA)

Idea: un script junta la evidencia de los libros, un modelo barato (Haiku) solo lee y responde con una cita textual, y otro script comprueba la cita en el libro. Lo que no se pueda comprobar se escala al revisor de siempre (REGLAS.md).

## Pasos de una tanda
1. Preparar paquetes (por banco, opcionalmente por semana):
   `python3 herramientas/rapido.py preparar <banco> [--semana N] [--tam 15] [--max 60]`
   Crea `verificacion/paquetes/<banco>/rNNN.json` (sin la clave) y `rNNN.claves.json`. Las preguntas con texto roto o sin clave van directo a `verificacion/escalar/<banco>/previas.json`.
2. Lanzar un modelo barato (Agent con `model: haiku`) por paquete, con el encargo de abajo (cambiar BANCO y rNNN). Se pueden lanzar varios en paralelo.
3. Comprobar cada respuesta:
   `python3 herramientas/rapido.py comprobar <banco> rNNN`
   Las aceptadas quedan en `verificacion/resultados/<banco>/rNNN.json` (estado `confirmada`) y el resto en `verificacion/escalar/<banco>/rNNN.json`.
4. Correr `python3 herramientas/verificar.py unir <banco>` y luego `construir.py` (como siempre).
5. Las de `escalar/` se verifican con el revisor normal (Agent caro): el archivo tiene el mismo formato que un lote, con el motivo y la pista del modelo barato (solo pista, no fuente).

Para medir la calidad antes de fiarse: `piloto <banco> --n 30` arma paquetes con preguntas ya verificadas; después de la respuesta del modelo, `comprobar _piloto-<banco> r001` compara con la respuesta verificada (las aceptadas deben coincidir al 100 %).

Nota: las preguntas ya enviadas a `escalar/` o en un paquete sin comprobar no se vuelven a preparar. Para reciclarlas, borra su archivo.
`comprobar --estricto` además exige que la cita mencione algún término de la opción elegida.

## Encargo para el modelo barato
```
Lee SOLO el archivo verificacion/paquetes/BANCO/rNNN.json (nada más del proyecto). No uses tu memoria ni internet.
Para cada pregunta, en el mismo orden: elige la opción que la evidencia del propio paquete respalda y copia TAL CUAL, sin cambiar ni una palabra, la frase (40 a 350 caracteres) de la evidencia que lo prueba. Si la evidencia no lo dice con claridad, o solo lo insinúa, responde decide:false y ans:null. No adivines.
Escribe verificacion/paquetes/BANCO/rNNN.respuesta.json: una lista JSON con un registro por pregunta:
{"k":"…","decide":true|false,"ans":índice desde 0 o null,"cita":{"libro":"sabiston","pagina":562,"texto":"frase copiada tal cual de la evidencia"},"why":"2 a 5 frases en español, para un principiante: por qué la correcta lo es y por qué las otras no","tema":"id de temas.json (el del paquete si no hay uno mejor)"}
Si decide es false, cita puede ser null y why explica qué falta. "libro" y "pagina" son los de la evidencia de donde copiaste la frase. Si la evidencia está en inglés, la cita va en inglés tal cual y el why en español.
Responde solo "listo" y el conteo (decididas / no decididas).
```

# Bancos de Cirugía (app para el celular)

## Las carpetas
| Carpeta | Qué hay | ¿Se publica? |
|---|---|---|
| `originales/` | Copias de tus PDF, HTML y fotos. **Aquí agregas bancos nuevos.** | No |
| `docs/` | La app ya armada (lo que ves en el celular) | Sí |
| `herramientas/` | Los programas que convierten los bancos | Sí (no tienen datos tuyos) |
| `bancos.json` | Nombre y orden de cada banco en el menú. Puedes cambiar los nombres aquí. | Sí |

## Agregar un banco nuevo
1. Copia el archivo a `originales/`:
   - un **HTML** interactivo, o
   - un **PDF** (si la respuesta está resaltada en amarillo o verde, la app la detecta), o
   - una **carpeta con fotos** de un examen (una carpeta = un banco).
2. Doble clic en **`Actualizar bancos.command`**. Aparece en el menú con el nombre del archivo.
   Si un PDF casi no tiene preguntas (un resumen), lo pone solo en la Biblioteca.
3. Si quieres otro nombre, edítalo en `bancos.json` y vuelve a hacer doble clic.
4. Publica los cambios (ver más abajo). El celular se actualiza solo la próxima vez que abras la app con internet.

## Verla en la Mac
Doble clic en **`Ver la app en mi Mac.command`**. Se abre en el navegador.

## Publicar los cambios en GitHub
Con GitHub Desktop: escribe un resumen (por ejemplo "Agrego banco X") → **Commit to main** → **Push origin**.

#!/bin/bash
# Doble clic: abre la app en el navegador de tu Mac. Para cerrarla, cierra esta ventana.
cd "$(dirname "$0")/docs"
(sleep 1; open "http://localhost:8765") &
echo "La app está en http://localhost:8765  —  cierra esta ventana para apagarla."
python3 -m http.server 8765

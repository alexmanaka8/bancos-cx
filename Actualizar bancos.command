#!/bin/bash
# Doble clic: vuelve a armar la app con lo que haya en la carpeta "originales".
cd "$(dirname "$0")"
python3 herramientas/construir.py
echo
read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."

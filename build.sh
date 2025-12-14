#!/usr/bin/env bash

# Bu, Aptfile'da belirtilen sistem bağımlılıklarının (ffmpeg, nodejs)
# kurulmasından sonra çalışır.

echo "Installing Python dependencies from requirements.txt..."
# requirements.txt içindeki tüm Python kütüphanelerini kur
pip install -r requirements.txt

echo "Build complete."

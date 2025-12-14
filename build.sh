#!/usr/bin/env bash

# 1. Python bağımlılıklarını kur (requirements.txt'den)
echo "Installing Python dependencies..."
pip install -r requirements.txt

# 2. FFmpeg'in yüklü olduğunu kontrol et (Aptfile'dan gelmeli)
if ! command -v ffmpeg &> /dev/null
then
    echo "FFmpeg could not be found. Check Aptfile."
    exit 1
fi

echo "Build complete. Starting deployment..."

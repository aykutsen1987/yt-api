#!/usr/bin/env bash

# 1. Python bağımlılıklarını kur (yt-dlp HARİÇ)
echo "Installing Python dependencies..."
pip install -r requirements.txt

# 2. yt-dlp'yi manual olarak indir ve çalıştırılabilir yap
echo "Installing yt-dlp binary..."
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
chmod a+rx /usr/local/bin/yt-dlp

echo "Build complete. Starting deployment..."

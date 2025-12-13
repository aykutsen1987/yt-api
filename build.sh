#!/bin/bash
set -e

echo "🚀 Starting build..."

# Sistem bağımlılıkları
apt-get update
apt-get install -y ffmpeg nodejs npm
echo "✅ FFmpeg & Node.js installed"

# Python bağımlılıkları
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Python packages installed"

echo "🎉 Build complete!"

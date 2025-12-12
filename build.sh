#!/bin/bash
# ============================================
# RENDER Build Script
# YouTube to MP3/M4A Converter API
# ============================================

set -e  # Exit on error

echo "🚀 Starting build process..."

# ✅ 1. System dependencies
echo "📦 Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y ffmpeg
    echo "✅ FFmpeg installed via apt-get"
else
    echo "⚠️ apt-get not available, skipping system packages"
fi

# ✅ 2. Verify FFmpeg
echo "🔍 Verifying FFmpeg installation..."
if command -v ffmpeg &> /dev/null; then
    ffmpeg -version | head -n 1
    echo "✅ FFmpeg is available"
else
    echo "❌ FFmpeg not found!"
    exit 1
fi

# ✅ 3. Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Python dependencies installed"

# ✅ 4. Verify installation
echo "🔍 Verifying Python packages..."
python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
python -c "import yt_dlp; print(f'yt-dlp: {yt_dlp.version.__version__}')"
echo "✅ Python packages verified"

# ✅ 5. Clean up
echo "🧹 Cleaning up..."
pip cache purge
echo "✅ Build complete!"

echo "🎉 Build successful! Ready to start server."

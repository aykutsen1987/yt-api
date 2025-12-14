#!/usr/bin/env bash

echo "Installing Python dependencies..."

# Kurulumu başlat
pip install -r requirements.txt

# Kurulumun başarılı olup olmadığını kontrol et
if [ $? -ne 0 ]; then
    echo "CRITICAL ERROR: pip installation failed. Check the logs above for the failing package."
    # Uygulamanın çökeceğini biliyoruz, ancak loglarda daha net bir mesaj bırakıyoruz.
    exit 1
fi

echo "Build complete."

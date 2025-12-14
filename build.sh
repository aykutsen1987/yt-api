#!/usr/bin/env bash

# 1. Python bağımlılıklarını kur (requirements.txt'den)
echo "Installing Python dependencies..."
pip install -r requirements.txt

# 2. Kurulumun tamamlandığını onayla
echo "Build complete. Starting deployment..."

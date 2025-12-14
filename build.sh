#!/usr/bin/env bash

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "CRITICAL ERROR: pip installation failed"
    exit 1
fi

echo "Build completed successfully."

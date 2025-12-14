#!/usr/bin/env bash

# 1. Python bağımlılıklarını kur (requirements.txt'den)
pip install -r requirements.txt

# 2. yt-dlp'yi pip ile kur (bu, FFmpeg bağımlılığını otomatik olarak kullanacaktır)
pip install yt-dlp

# 3. Opsiyonel: Dosyalara çalıştırma izni ver (eğer bir yerel binary kullanılıyorsa)
# chmod +x /usr/local/bin/yt-dlp 
# chmod +x /usr/bin/ffmpeg 

echo "Build tamamlandı. YT-DLP ve FFmpeg hazır."

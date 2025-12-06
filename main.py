import os # Ortam değişkenlerini okumak için
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

# ... (VideoRequest sınıfı ve diğer kodlar)

@app.post("/api/yt")
async def get_video_info(data: VideoRequest):
    # Ortam değişkeninden çerezleri çek
    youtube_cookies = os.environ.get("YOUTUBE_COOKIES", None)
    
    # yt-dlp ayarlarını oluştur
    ydl_opts = {
        "quiet": True, 
        "skip_download": True, 
        # ... diğer format ayarları
    }
    
    # Çerezler varsa, yt-dlp'ye ilet
    if youtube_cookies:
        ydl_opts['cookie'] = youtube_cookies # yt-dlp'nin çerezleri kullanmasını sağla
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # ... (info = ydl.extract_info(data.url, download=False) kısmı devam eder)
            info = ydl.extract_info(data.url, download=False)
            return {"title": info.get("title"), "formats": info.get("formats")}
    except Exception as e:
        return {"error": str(e)}

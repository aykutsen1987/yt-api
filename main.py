from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp
import uvicorn

app = FastAPI()

# Gelen istek gövdesinin yapısını tanımlar (Örn: {"url": "https://youtu.be/..."})
class VideoRequest(BaseModel):
    url: str

@app.post("/api/yt")
async def get_video_info(data: VideoRequest):
    """
    Belirtilen YouTube URL'sinden video başlığını ve mevcut formatları (akış URL'leri dahil) çeker.
    """
    if not data.url:
        raise HTTPException(status_code=400, detail="URL alanı boş olamaz.")
        
    try:
        # yt-dlp ayarları: Sessiz çalış, indirmeyi atla, sadece bilgi çek
        ydl_opts = {
            "quiet": True, 
            "skip_download": True, 
            "format": "bestaudio/best", # Sadece en iyi ses formatlarını önceliklendir
            "noplaylist": True, # Oynatma listesi indirmeyi engelle
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Bilgiyi çek
            info = ydl.extract_info(data.url, download=False)
            
            # Ses akış URL'sini bulma (Opsiyonel: Daha sonra mobil uygulamada bu format listesinden çekilebilir)
            audio_formats = [
                f for f in info.get("formats", []) 
                if f.get("vcodec") == "none" and f.get("ext") in ["m4a", "webm"]
            ]

            return {
                "title": info.get("title"), 
                "formats": audio_formats, 
                "thumbnail": info.get("thumbnail"),
                # Mobil uygulamanızın kullanabileceği tüm formatları listeler
            }
            
    except Exception as e:
        # Hata durumunda (Örn: Video bulunamadı, telif hakkı engeli, vb.)
        error_message = f"Video bilgileri çekilirken hata oluştu: {e}"
        raise HTTPException(status_code=500, detail=error_message)

# Eğer main.py doğrudan çalıştırılırsa, Uvicorn ile başlat
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

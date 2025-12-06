import os
import yt_dlp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class VideoRequest(BaseModel):
    url: str

app = FastAPI()

@app.post("/api/yt")
async def get_video_info(data: VideoRequest):
    youtube_cookies = os.environ.get("YOUTUBE_COOKIES", None)
    
    ydl_opts = {
        "quiet": True, 
        "skip_download": True,
        "format": "bestaudio/best",
        "extractor_args": ["youtube:player_client=default"],
    }
    
    if youtube_cookies:
        ydl_opts['cookie'] = youtube_cookies
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=False)
            
            # -----------------------------------------------------------------
            # 🔥 GÜVENLİK KONTROLÜ VE LİSTE DÜZELTMESİ (Bu kısmı güncelleyin)
            # -----------------------------------------------------------------
            # 1. Eğer yt-dlp bir videolar listesi döndürdüyse (örneğin çalma listesinden)
            if isinstance(info, list):
                if not info:
                    raise ValueError("Çalma listesi/kanal boş veya erişilebilir video içermiyor.")
                # Listenin ilk elemanını (ilk videoyu) al
                info = info[0]
            
            # 2. Önceki STR kontrolünü koru
            if not isinstance(info, dict):
                # Eğer info hâlâ bir sözlük değilse (str, None vb.) hata fırlat.
                raise ValueError(f"yt-dlp beklenmedik bir format döndürdü. Yanıt tipi: {type(info).__name__}. Çerezler geçersiz olabilir.")
            
            # -----------------------------------------------------------------
            # Normal Veri İşleme Devam Ediyor
            # -----------------------------------------------------------------
            stream_url = info.get('url')
            
            if not stream_url:
                raise ValueError("Video için geçerli bir akış URL'si bulunamadı. Video silinmiş, özel veya coğrafi engelli olabilir.")
                
            return {
                "title": info.get("title", "Başlık Yok"),
                "audio": stream_url, 
                "video": "",
                "thumbnail": info.get("thumbnail") 
            }
            
    except Exception as e:
        error_detail = f"Video bilgileri çekilirken hata oluştu: {e}"
        raise HTTPException(status_code=500, detail=error_detail)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "YouTube Stream API is running."}

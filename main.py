import os
import yt_dlp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# POST isteği için veri modeli
class VideoRequest(BaseModel):
    url: str

app = FastAPI()

@app.post("/api/yt")
async def get_video_info(data: VideoRequest):
    youtube_cookies = os.environ.get("YOUTUBE_COOKIES", None)
    
    ydl_opts = {
        "quiet": True, 
        "skip_download": True,
        "format": "bestaudio/best", # En iyi ses akışını seçer
        # Kararlılık ve bot engeli için önerilen parametreler:
        "extractor_args": ["youtube:player_client=default"],
    }
    
    if youtube_cookies:
        ydl_opts['cookie'] = youtube_cookies
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Video bilgilerini çeker
            info = ydl.extract_info(data.url, download=False)
            
            # 🔥 KRİTİK DÜZELTME: Gelen verinin bir liste olup olmadığını kontrol et.
            # Eğer bir liste ise (çalma listesi/kanal URL'si gönderilmişse), 
            # listenin ilk öğesini al (ilk video).
            if isinstance(info, list):
                if not info:
                    raise ValueError("Çalma listesi/kanal boş veya erişilebilir video içermiyor.")
                info = info[0] # Listenin ilk video objesini alıyoruz.
            
            # GÜVENLİK KONTROLÜ: Gelen verinin bir sözlük (dict) olduğundan emin ol.
            # Bu, 'str' object has no attribute 'get' hatasını çözer.
            if not isinstance(info, dict):
                raise ValueError(f"yt-dlp beklenmedik bir format döndürdü. Yanıt tipi: {type(info).__name__}. Çerezler geçersiz olabilir.")
            
            # Normal Veri İşleme Devam Ediyor
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

# Sunucu durum kontrolü
@app.get("/")
def read_root():
    return {"status": "ok", "message": "YouTube Stream API is running."}

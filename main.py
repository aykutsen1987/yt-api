import os
import yt_dlp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --------------------------
# 1. Pydantic Veri Modeli
# --------------------------
# FastAPI'ye POST isteğinde beklenen JSON yapısını tanımlar: {"url": "..."}
class VideoRequest(BaseModel):
    url: str

app = FastAPI()

# --------------------------
# 2. Ana Uç Nokta (Endpoint)
# --------------------------
@app.post("/api/yt")
async def get_video_info(data: VideoRequest):
    # Ortam Değişkeninden YOUTUBE_COOKIES değerini çeker.
    # Eğer tanımlı değilse None olur.
    youtube_cookies = os.environ.get("YOUTUBE_COOKIES", None)
    
    # yt-dlp ayarları (options)
    ydl_opts = {
        "quiet": True, 
        "skip_download": True,  # Sadece bilgi ve stream URL'si çekilecek, dosya indirilmeyecek.
        "format": "bestaudio/best", # En iyi ses akışını seçer (.m4a veya .webm).
        
        # Kararlılık ve bot engeli için önerilen parametreler:
        "extractor_args": ["youtube:player_client=default"],
    }
    
    # Eğer çerez Ortam Değişkeni tanımlıysa, yt-dlp ayarına ekler.
    if youtube_cookies:
        ydl_opts['cookie'] = youtube_cookies
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Video bilgilerini çeker
            info = ydl.extract_info(data.url, download=False)
            
            # 🔥 GÜVENLİK KONTROLÜ: Gelen verinin sözlük (dict) olduğundan emin ol.
            # 'str' object has no attribute 'get' hatasını kesin olarak çözer.
            if not isinstance(info, dict):
                 # Eğer info bir dizeyse, bunu hataya dahil et
                raise ValueError(f"yt-dlp beklenmedik bir format döndürdü. Yanıt tipi: {type(info).__name__}. Muhtemel neden: Çerezler geçersiz veya video engelli.")
            
            # Oynatılacak en uygun URL'yi info objesinden güvenli bir şekilde çekiyoruz.
            stream_url = info.get('url')
            
            if not stream_url:
                # URL bulunamadıysa, bir hata fırlat.
                raise ValueError("Video için geçerli bir akış URL'si bulunamadı. Video silinmiş olabilir.")
                
            # API'nin Android uygulamanızın beklediği formata göre JSON döndürür
            return {
                "title": info.get("title", "Başlık Yok"),
                "audio": stream_url, 
                "video": "", # Sadece ses istendiği için boş bırakıldı
                "thumbnail": info.get("thumbnail") 
            }
            
    except Exception as e:
        # Hata oluşursa 500 hatası döndürür ve loglarda çıkan hatayı detay olarak gösterir.
        error_detail = f"Video bilgileri çekilirken hata oluştu: {e}"
        # Redbin'e geri dönecek hatayı fırlat
        raise HTTPException(status_code=500, detail=error_detail)

# --------------------------
# 3. Root Endpoint (Sunucu Sağlığını Kontrol Etmek İçin)
# --------------------------
@app.get("/")
def read_root():
    return {"status": "ok", "message": "YouTube Stream API is running."}

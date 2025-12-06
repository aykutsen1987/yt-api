import os
import yt_dlp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --------------------------
# 1. PYDANTIC VERI MODELLERİ
# --------------------------
# FastAPI'ye POST isteğinde beklenen JSON yapısını tanımlar: {"url": "..."}
class VideoRequest(BaseModel):
    url: str

app = FastAPI()

# --------------------------
# 2. ANA UÇ NOKTA (ENDPOINT)
# --------------------------
@app.post("/api/yt")
async def get_video_info(data: VideoRequest):
    # Ortam Değişkeninden YOUTUBE_COOKIES değerini çeker.
    # (Sizin Render panelinizde tanımladığınız çerez dizesi)
    youtube_cookies = os.environ.get("YOUTUBE_COOKIES", None)
    
    # yt-dlp ayarları (options)
    ydl_opts = {
        # Çıktı vermeyi engeller, logları temiz tutar.
        "quiet": True, 
        # Sadece bilgi çeker, video indirmeyi atlar.
        "skip_download": True, 
        # Çözümlemeyi hızlandırmak için sadece ses formatlarını seçer.
        "format": "bestaudio",
        # Geçici çözüm: JS runtime uyarısını gidermek için (daha önce konuşulmuştu).
        "extractor_args": "youtube:player_client=default", 
    }
    
    # Eğer çerez Ortam Değişkeni tanımlıysa, yt-dlp ayarına ekler.
    if youtube_cookies:
        ydl_opts['cookie'] = youtube_cookies
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Video bilgilerini çeker
            info = ydl.extract_info(data.url, download=False)
            
            # Yt-dlp, "bestaudio" formatını seçtiğinde genellikle 'url', 'title' vb. alanlarını doldurur.
            # En iyi akış URL'sini ve meta verileri API yanıtı olarak döndürürüz.
            
            # NOT: Eğer backend'iniz sadece tek bir URL döndürecekse, 
            # en iyi ses formatının URL'sini doğrudan çekmelisiniz.
            
            # Eğer info['url'] en iyi ses URL'sini temsil ediyorsa:
            stream_url = info.get('url')
            
            # VEYA, formats listesinden en iyi ses URL'sini çekmek isterseniz:
            # stream_url = info.get('formats')[0].get('url') # En üstteki formatı alır
            
            # API'nin Android uygulamanızın beklediği formata göre JSON döndürür
            return {
                "title": info.get("title", "Başlık Yok"),
                "audio": stream_url, 
                # Video akışına ihtiyacınız yoksa 'video' alanını silin, 
                # ancak mobil uygulamanız bekliyorsa şimdilik boş bırakın.
                "video": "", 
                "thumbnail": info.get("thumbnail") 
            }
            
    except Exception as e:
        # Hata oluşursa 500 hatası döndürür ve loglarda çıkan hatayı detay olarak gösterir.
        # Bu, Android tarafında hata ayıklamayı kolaylaştırır.
        error_detail = f"Video bilgileri çekilirken hata oluştu: {e}"
        raise HTTPException(status_code=500, detail=error_detail)

# --------------------------
# 3. ROOT ENDPOINT (İsteğe Bağlı)
# --------------------------
# Sunucunun çalışıp çalışmadığını kontrol etmek için basit bir endpoint
@app.get("/")
def read_root():
    return {"status": "ok", "message": "YouTube Stream API is running."}

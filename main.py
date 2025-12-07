import os
import tempfile
import logging
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from pydantic import BaseModel, HttpUrl

# --- Temel Yapılandırma ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Ses API",
    description="YouTube videolarını dinlemek (stream) ve indirmek (download) için bir API.",
    version="2.0.0",
)

# --- Pydantic Modelleri ---
class VideoInfo(BaseModel):
    title: str
    thumbnail: str
    duration: int
    stream_url: HttpUrl # Dinleme için kullanılacak URL

# --- Çerez Yönetimi ---
YOUTUBE_COOKIES = os.environ.get("YOUTUBE_COOKIES")

def create_cookie_file():
    """Ortam değişkenindeki çerezleri geçici bir dosyaya yazar ve dosya yolunu döndürür."""
    if not YOUTUBE_COOKIES:
        return None
    
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', suffix='.txt') as temp_cookie_file:
            temp_cookie_file.write(YOUTUBE_COOKIES)
            logger.info(f"Çerez dosyası oluşturuldu: {temp_cookie_file.name}")
            return temp_cookie_file.name
    except Exception as e:
        logger.error(f"Geçici çerez dosyası oluşturulamadı: {e}")
        return None

def cleanup_cookie_file(file_path: str):
    """Verilen yoldaki geçici çerez dosyasını siler."""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Çerez dosyası silindi: {file_path}")
        except Exception as e:
            logger.error(f"Geçici çerez dosyası silinemedi: {e}")

def sanitize_filename(title: str) -> str:
    """Dosya adı için geçersiz karakterleri temizler."""
    # Geçersiz karakterleri kaldır
    sanitized = re.sub(r'[\\/*?:"<>|]', "", title)
    # Çok uzunsa kısalt
    return (sanitized[:100] + '..') if len(sanitized) > 100 else sanitized

def get_audio_url_from_youtube(video_url: str) -> dict:
    """yt-dlp kullanarak bir videonun başlığını ve en iyi ses URL'sini alır."""
    cookie_file_path = create_cookie_file()
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_file_path,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            if not info:
                raise DownloadError("Video bilgileri alınamadı (boş yanıt).")

            # En iyi ses formatını bulmaya çalış
            audio_url = None
            if 'formats' in info and info['formats']:
                audio_formats = [
                    f for f in info['formats'] 
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url')
                ]
                if audio_formats:
                    audio_url = audio_formats[-1]['url'] # Genellikle en iyi kalite sonda olur

            # Format listesinde bulamazsa, ana URL'yi dene
            if not audio_url:
                audio_url = info.get('url')
            
            if not audio_url:
                raise DownloadError("Uygun bir ses akış URL'si bulunamadı.")

            return {
                "title": info.get("title", "Baslik Yok"),
                "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration", 0),
                "audio_url": audio_url,
            }
            
    except DownloadError as e:
        logger.error(f"yt-dlp hatası: {e}")
        if "HTTP Error 429" in str(e):
            raise HTTPException(status_code=429, detail="YouTube'a çok fazla istek gönderildi. Lütfen çerezlerinizi güncelleyin veya bir süre bekleyin.")
        raise HTTPException(status_code=404, detail=f"Video bilgileri çekilemedi. URL geçersiz veya video kısıtlı olabilir. Hata: {e}")
    except Exception as e:
        logger.error(f"Beklenmedik bir hata oluştu: {e}")
        raise HTTPException(status_code=500, detail=f"Sunucuda beklenmedik bir hata oluştu: {e}")
    finally:
        cleanup_cookie_file(cookie_file_path)

# --- API Endpoints ---

@app.get("/info", response_model=VideoInfo, summary="Video Bilgilerini ve Dinleme Linkini Al")
def get_info_endpoint(url: HttpUrl = Query(..., description="Bilgisi alınacak YouTube video URL'si")):
    """
    Bir YouTube videosunun başlık, küçük resim, süre ve **dinleme (stream)**
    için kullanılacak ses akış URL'sini JSON formatında döndürür.
    Mobil uygulamanızda bir müzik çalıcıyı beslemek için bu endpoint'i kullanın.
    """
    if "youtube.com" not in str(url) and "youtu.be" not in str(url):
        raise HTTPException(status_code=400, detail="Lütfen geçerli bir YouTube URL'si girin.")

    data = get_audio_url_from_youtube(str(url))
    
    return VideoInfo(
        title=data["title"],
        thumbnail=data["thumbnail"],
        duration=data["duration"],
        stream_url=data["audio_url"]
    )

@app.get("/download", response_class=RedirectResponse, summary="MP3 İndirme Linki Oluştur")
def download_endpoint(url: HttpUrl = Query(..., description="İndirilecek YouTube video URL'si")):
    """
    Bir YouTube videosunun sesini MP3 olarak indirmek için kullanıcıyı
    doğrudan indirme linkine yönlendirir. Tarayıcıda veya indirme yöneticisinde
    kullanıldığında dosyayı indirmeyi tetikler.
    """
    if "youtube.com" not in str(url) and "youtu.be" not in str(url):
        raise HTTPException(status_code=400, detail="Lütfen geçerli bir YouTube URL'si girin.")

    data = get_audio_url_from_youtube(str(url))
    
    # İndirme linkini al
    download_url = data["audio_url"]
    
    # İndirilecek dosya için temiz bir isim oluştur
    clean_title = sanitize_filename(data["title"])
    filename = f"{clean_title}.mp3"
    
    # Yönlendirme yanıtı oluştur. Content-Disposition başlığı, tarayıcıya
    # bu linki açmak yerine indirmesini ve dosya adını ne koyacağını söyler.
    # Ancak, FastAPI'nin RedirectResponse'u doğrudan başlık eklemeyi karmaşıklaştırır.
    # En basit ve en uyumlu yöntem, doğrudan yönlendirmektir.
    # İstemci bu yönlendirmeyi takip ettiğinde indirme başlayacaktır.
    
    # Not: Bazı ses URL'leri zaten indirmeyi tetikleyen başlıklar içerir.
    logger.info(f"'{data['title']}' için indirme yönlendirmesi yapılıyor: {download_url}")
    return RedirectResponse(url=download_url)

@app.get("/")
def read_root():
    return {"message": "YouTube Ses API'sine hoş geldiniz. /info veya /download endpoint'lerini kullanın."}


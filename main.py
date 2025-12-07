import os
import tempfile
import logging
from fastapi import FastAPI, HTTPException, Query
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from pydantic import BaseModel, HttpUrl

# Günlük (logging) yapılandırması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Ses Akışı API",
    description="yt-dlp ve çerez desteği ile YouTube videolarından ses akış URL'lerini çeken bir API.",
    version="1.0.0",
)

# Pydantic ile yanıt modelini tanımlama
class VideoInfo(BaseModel):
    title: str
    thumbnail: str
    audio_url: HttpUrl
    duration: int

# Çerezleri ortam değişkeninden al
# Render'da YOUTUBE_COOKIES adında bir ortam değişkeni oluşturup
# tarayıcınızdan aldığınız çerezleri (Netscape formatında) buraya yapıştırın.
YOUTUBE_COOKIES = os.environ.get("YOUTUBE_COOKIES")

def get_video_info(video_url: str) -> dict:
    """
    Verilen YouTube URL'si için video bilgilerini çeker.
    Çerezleri geçici bir dosyaya yazarak yt-dlp'ye verir.
    """
    cookie_file_path = None
    if YOUTUBE_COOKIES:
        # Geçici bir dosya oluşturup çerezleri içine yaz
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as temp_cookie_file:
            temp_cookie_file.write(YOUTUBE_COOKIES)
            cookie_file_path = temp_cookie_file.name
        logger.info(f"Çerezler geçici olarak şu dosyaya yazıldı: {cookie_file_path}")

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True, # Sadece temel bilgileri hızlıca al
        'force_generic_extractor': True,
    }

    if cookie_file_path:
        ydl_opts['cookiefile'] = cookie_file_path

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # extract_info senkron bir işlemdir, FastAPI bunu bir thread pool'da çalıştırır.
            info = ydl.extract_info(video_url, download=False)
            
            if not info:
                raise DownloadError("Video bilgileri alınamadı (boş yanıt).")

            # En iyi ses formatını bul
            # extract_flat kullanıldığında formatlar listesi gelmez, doğrudan URL'i ararız.
            # Bu yüzden extract_flat'i kapatıp, formatları listeletmek daha güvenilir olabilir.
            # Daha detaylı bilgi için ydl_opts'u güncelleyelim.
            
    except Exception as e:
        logger.error(f"İlk bilgi çekme denemesinde hata: {e}")
        # İlk deneme başarısız olursa, daha detaylı bir deneme yap
        pass
    finally:
        # Geçici çerez dosyasını her zaman sil
        if cookie_file_path and os.path.exists(cookie_file_path):
            os.remove(cookie_file_path)
            logger.info(f"Geçici çerez dosyası silindi: {cookie_file_path}")


    # Daha detaylı bilgi almak için ikinci, daha yavaş deneme
    ydl_opts_detailed = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    if YOUTUBE_COOKIES:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as temp_cookie_file:
            temp_cookie_file.write(YOUTUBE_COOKIES)
            cookie_file_path = temp_cookie_file.name
        ydl_opts_detailed['cookiefile'] = cookie_file_path

    try:
        with YoutubeDL(ydl_opts_detailed) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                 raise DownloadError("Video bilgileri alınamadı (boş yanıt).")

            audio_format = None
            # 'formats' listesini kontrol et
            if 'formats' in info and info['formats']:
                for f in info['formats']:
                    # Sadece ses içeren ve URL'si olan bir format ara
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url'):
                        audio_format = f
                        break
            
            # Eğer format bulunamazsa, ilk sıradaki URL'i dene
            if not audio_format:
                 audio_url = info.get('url')
                 if not audio_url:
                     raise DownloadError("Uygun bir ses akış URL'si bulunamadı.")
            else:
                audio_url = audio_format.get('url')


            return {
                "title": info.get("title", "Başlık Yok"),
                "thumbnail": info.get("thumbnail", ""),
                "audio_url": audio_url,
                "duration": info.get("duration", 0),
            }
            
    except DownloadError as e:
        logger.error(f"yt-dlp hatası: {e}")
        if "HTTP Error 429" in str(e):
            raise HTTPException(status_code=429, detail="Çok fazla istek gönderildi. Lütfen daha sonra tekrar deneyin.")
        raise HTTPException(status_code=404, detail=f"Video bilgileri çekilemedi. URL geçersiz veya video kısıtlı olabilir. Hata: {e}")
    except Exception as e:
        logger.error(f"Beklenmedik bir hata oluştu: {e}")
        raise HTTPException(status_code=500, detail=f"Sunucuda beklenmedik bir hata oluştu: {e}")
    finally:
        # Geçici çerez dosyasını her zaman sil
        if cookie_file_path and os.path.exists(cookie_file_path):
            os.remove(cookie_file_path)
            logger.info(f"Geçici çerez dosyası silindi: {cookie_file_path}")


@app.get("/info", response_model=VideoInfo)
def get_info(url: HttpUrl = Query(..., description="Ses akışı alınacak YouTube video URL'si")):
    """
    Bir YouTube video URL'si alır ve videonun başlığını, küçük resmini,
    süresini ve en iyi kalitedeki ses akışının URL'sini döndürür.
    """
    if "youtube.com" not in str(url) and "youtu.be" not in str(url):
        raise HTTPException(status_code=400, detail="Lütfen geçerli bir YouTube URL'si girin.")

    video_info = get_video_info(str(url))
    return video_info

@app.get("/")
def read_root():
    return {"message": "YouTube Ses Akışı API'sine hoş geldiniz. Bilgi almak için /info endpoint'ini kullanın."}


import os
import asyncio
import subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import yt_dlp
import logging
from yt_dlp.utils import DownloadError, ExtractorError

# --- Yapılandırma ---
COOKIES_FILE = Path("cookies.txt")

if not COOKIES_FILE.exists():
    COOKIES_FILE.touch()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Pydantic Modelleri ---

class CookieRequest(BaseModel):
    cookies: str

class MP3Request(BaseModel):
    url: str

class ErrorResponse(BaseModel):
    status: str = "error"
    message: str

# --- yt-dlp Ayarları (Streaming için değiştirildi) ---

YDL_OPTS = {
    # Akış için sadece bilgiyi çekeceğiz, indirme yapmayacağız
    "format": "bestaudio",
    "noplaylist": True,
    "nocheckcertificate": True,
    "cookies": str(COOKIES_FILE),
    "extractor_args": {
        "youtube": {
            "player_client": "default"
        }
    },
    "quiet": True,
    "no_warnings": True,
}

# --- FastAPI Uygulaması ---

app = FastAPI(
    title="YouTube MP3 Streamer API",
    description="Render üzerinde çalışan, yt-dlp tabanlı YouTube MP3 Akış API'si."
)

# --- Yardımcı Fonksiyonlar ---

async def run_blocking_operation(func, *args, **kwargs):
    """Bloklayan fonksiyonları ayrı bir thread'de çalıştırır."""
    return await asyncio.to_thread(func, *args, **kwargs)

# --- Endpoint'ler ---

@app.get("/health", summary="Sunucu durum kontrolü.")
def health_check():
    """Basit durum kontrolü (Health Check)."""
    return {"status": "ok", "service": "YouTube MP3 Streamer"}

@app.post(
    "/update_cookies",
    summary="YouTube çerezlerini günceller ve kaydeder.",
    status_code=status.HTTP_200_OK
)
async def update_cookies(data: CookieRequest):
    """
    Android uygulaması tarafından gönderilen çerezleri cookies.txt dosyasına kaydeder.
    """
    try:
        # Çerez dizesini direkt olarak dosyaya yazma
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write(data.cookies)
        
        logging.info("YouTube çerezleri güncellendi.")
        return {"status": "ok", "message": "Çerezler başarıyla kaydedildi."}
    except Exception as e:
        logging.error(f"Çerez kaydetme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(message="Çerezler kaydedilirken bir hata oluştu.").dict()
        )

# Jeneratör fonksiyonu, ses çıktısını parça parça yakalar
async def generate_audio_stream(url: str):
    """
    yt-dlp'yi harici bir süreç olarak çalıştırır ve ses çıktısını yakalar.
    """
    logging.info(f"Akış başlatılıyor: {url}")
    
    # yt-dlp'yi çalıştırırken çıktıyı stdout'a yönlendiriyoruz
    # --no-progress: İlerlemeyi gösterme
    # -o -: Çıktıyı stdout'a yönlendir
    # --cookies: cookies.txt dosyasını kullan
    
    # yt-dlp komutunu oluştururken tüm ayarları dahil etmeliyiz
    cmd = [
        "yt-dlp", 
        url,
        "-f", "bestaudio", 
        "--no-progress", 
        "-o", "-",
        "--cookies", str(COOKIES_FILE)
    ]
    
    # Akış yanıtı için process'i başlat
    try:
        # asyncio.create_subprocess_exec kullanılarak non-blocking process başlatılır
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Çıktıyı parça parça oku ve yield et
        while True:
            chunk = await process.stdout.read(4096)
            if not chunk:
                break
            yield chunk

        # İşlemin sonlanmasını bekle ve dönüş kodunu kontrol et
        await process.wait()
        
        if process.returncode != 0:
            stderr = await process.stderr.read()
            stderr_str = stderr.decode('utf-8', errors='ignore')
            
            # yt-dlp hatalarını yakalamaya çalış
            error_message = f"yt-dlp akış hatası. Hata kodu: {process.returncode}. Detay: {stderr_str.split('ERROR: ')[-1].strip()}"
            logging.error(error_message)
            raise DownloadError(error_message)

    except DownloadError as e:
        # Hata jeneratör içinde oluştuğunda, bu hata FastAPI'de 
        # düzgün yakalanamaz. Bu yüzden en iyi strateji, yanıt 
        # başlatılmadan önce bilgiyi çekmektir.
        logging.error(f"Akış sırasında DownloadError: {e}")
        # Burada bir HTTP yanıtı döndüremeyiz, bu yüzden process'i sonlandırıp 
        # istemcinin bağlantıyı kesmesini bekleyeceğiz.

    except Exception as e:
        logging.error(f"Beklenmeyen akış hatası: {e}")
        # Bağlantıyı kes

@app.post(
    "/listen",
    summary="YouTube URL'sindeki sesi doğrudan akış olarak döndürür.",
)
async def stream_audio(data: MP3Request):
    """
    Gönderilen YouTube URL'sindeki sesi bir HTTP akışı olarak (StreamingResponse) döndürür.
    """
    url = data.url
    
    try:
        # 1. Video Bilgilerini Çekme (Hata Kontrolü)
        # Akış başlamadan önce URL'nin geçerli olduğunu ve çerezlerin çalıştığını kontrol etmeliyiz.
        # Bu, akış başladıktan sonra hata vermemek için kritik.
        ydl_info = yt_dlp.YoutubeDL(YDL_OPTS | {"skip_download": True, "force_generic_extractor": True})
        
        # Blocking call, must be run in a separate thread
        info_dict = await run_blocking_operation(ydl_info.extract_info, url, download=False)
        
        # Eğer bir hata yoksa, devam et
        logging.info(f"Başlık: {info_dict.get('title')}. Akış başlatılıyor.")
        
        # 2. Streaming Başlatma
        
        # Content-Type'ı ses (audio) olarak ayarlıyoruz. MP3 formatı için 'audio/mpeg' en yaygın olanıdır.
        return StreamingResponse(
            generate_audio_stream(url), 
            media_type="audio/mpeg"
        )

    except (DownloadError, ExtractorError) as e:
        # yt-dlp hatalarını (Engelleme, Çerez vb.) yakalar
        error_message = f"YouTube indirme/işleme hatası: {str(e).split('ERROR: ')[-1].split(';')[0]}"
        logging.error(error_message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(message=error_message).dict()
        )
    except Exception as e:
        error_message = f"Beklenmeyen sunucu hatası: {str(e)}"
        logging.error(error_message, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(message=error_message).dict()
        )

# --- Uvicorn Çalıştırma Talimatı ---

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")

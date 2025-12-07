from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import logging
from pathlib import Path
import traceback

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI uygulaması
app = FastAPI(
    title="YouTube MP3 API",
    version="1.0.0",
    description="YouTube videolarını MP3 formatına dönüştürme API'si"
)

# CORS ayarları (Android için önemli)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Downloads klasörünü oluştur
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)
logger.info(f"Downloads klasörü oluşturuldu: {DOWNLOADS_DIR.absolute()}")

# Cookies dosyası
COOKIES_FILE = Path("cookies.txt")

# Statik dosya servisi - downloads klasörü için
try:
    app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")
    logger.info("Statik dosya servisi başlatıldı: /downloads")
except Exception as e:
    logger.error(f"Statik dosya servisi başlatılamadı: {e}")

# Request modelleri
class CookieRequest(BaseModel):
    cookies: str

class MP3Request(BaseModel):
    url: str

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global hata: {str(exc)}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": str(exc),
            "path": str(request.url)
        }
    )

# yt-dlp ayarları
def get_ydl_opts():
    opts = {
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": "mp3",
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "noplaylist": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["default", "web"]
            }
        },
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": False,
        "no_warnings": False,
    }
    
    # Cookie varsa ekle
    if COOKIES_FILE.exists():
        opts["cookies"] = str(COOKIES_FILE)
        logger.info(f"Cookie dosyası kullanılıyor: {COOKIES_FILE}")
    else:
        logger.warning("Cookie dosyası bulunamadı")
    
    return opts

@app.get("/")
async def root():
    """Ana sayfa - API bilgileri"""
    return {
        "status": "online",
        "message": "YouTube MP3 API çalışıyor",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health - Sağlık kontrolü",
            "update_cookies": "POST /update_cookies - Cookie güncelleme",
            "mp3": "POST /mp3 - YouTube videosu indir",
            "list": "GET /list - İndirilen dosyaları listele"
        },
        "example": {
            "update_cookies": {
                "method": "POST",
                "url": "/update_cookies",
                "body": {"cookies": "HSID=xxx; SID=yyy"}
            },
            "download": {
                "method": "POST",
                "url": "/mp3",
                "body": {"url": "https://www.youtube.com/watch?v=VIDEO_ID"}
            }
        }
    }

@app.get("/health")
async def health_check():
    """Sunucu sağlık kontrolü"""
    try:
        cookie_exists = COOKIES_FILE.exists()
        downloads_count = len(list(DOWNLOADS_DIR.glob("*.mp3")))
        
        # FFmpeg kontrolü
        ffmpeg_available = os.system("ffmpeg -version > /dev/null 2>&1") == 0
        
        return {
            "status": "healthy",
            "timestamp": str(Path.cwd()),
            "cookies": {
                "exists": cookie_exists,
                "path": str(COOKIES_FILE.absolute()) if cookie_exists else None
            },
            "downloads": {
                "dir": str(DOWNLOADS_DIR.absolute()),
                "count": downloads_count
            },
            "ffmpeg": "available" if ffmpeg_available else "not_found"
        }
    except Exception as e:
        logger.error(f"Health check hatası: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

@app.post("/update_cookies")
async def update_cookies(request: CookieRequest):
    """
    Android uygulamasından gelen cookie'leri kaydet
    """
    try:
        cookies = request.cookies.strip()
        
        if not cookies:
            raise HTTPException(status_code=400, detail="Cookie verisi boş olamaz")
        
        logger.info(f"Cookie güncelleme isteği alındı (uzunluk: {len(cookies)})")
        
        # Cookie'yi Netscape formatında kaydet
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# Generated by YouTube MP3 API\n\n")
            
            # Cookie'leri parse et
            for cookie in cookies.split(";"):
                cookie = cookie.strip()
                if "=" in cookie:
                    key, value = cookie.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Netscape format: domain, flag, path, secure, expiration, name, value
                    f.write(f".youtube.com\tTRUE\t/\tTRUE\t0\t{key}\t{value}\n")
        
        logger.info(f"Cookie başarıyla kaydedildi: {COOKIES_FILE}")
        
        return {
            "status": "success",
            "message": "Cookie'ler başarıyla güncellendi",
            "file": str(COOKIES_FILE.absolute()),
            "cookies_count": len(cookies.split(";"))
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cookie kaydetme hatası: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Cookie kaydetme hatası: {str(e)}")

@app.post("/mp3")
async def download_mp3(request: MP3Request):
    """
    YouTube videosunu MP3 olarak indir
    """
    try:
        url = request.url.strip()
        
        # URL validasyonu
        if not url:
            raise HTTPException(status_code=400, detail="URL boş olamaz")
        
        if "youtube.com" not in url and "youtu.be" not in url:
            raise HTTPException(
                status_code=400, 
                detail="Geçerli bir YouTube URL'si giriniz (youtube.com veya youtu.be)"
            )
        
        logger.info(f"İndirme isteği: {url}")
        
        # yt-dlp ile video bilgilerini al
        ydl_opts = get_ydl_opts()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Video bilgilerini çek
                logger.info("Video bilgileri çekiliyor...")
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise HTTPException(status_code=404, detail="Video bilgileri alınamadı")
                
                video_id = info.get("id")
                title = info.get("title", "Unknown")
                duration = info.get("duration", 0)
                
                logger.info(f"Video: {title} ({video_id}) - {duration}s")
                
                # MP3 dosya yolu
                mp3_file = DOWNLOADS_DIR / f"{video_id}.mp3"
                
                # Dosya zaten varsa
                if mp3_file.exists():
                    logger.info(f"Dosya cache'de bulundu: {mp3_file.name}")
                    file_size = mp3_file.stat().st_size
                    
                    # Base URL
                    base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
                    audio_url = f"{base_url}/downloads/{video_id}.mp3"
                    
                    return {
                        "status": "ok",
                        "cached": True,
                        "title": title,
                        "duration": duration,
                        "file_size": file_size,
                        "audio_url": audio_url,
                        "video_id": video_id
                    }
                
                # Video indir
                logger.info("Video indiriliyor...")
                ydl.download([url])
                
                # İndirilen dosyayı kontrol et
                if not mp3_file.exists():
                    # Bazen dosya ismi farklı olabiliyor
                    possible_files = list(DOWNLOADS_DIR.glob(f"{video_id}.*"))
                    if possible_files:
                        mp3_file = possible_files[0]
                        logger.info(f"Dosya farklı uzantıyla bulundu: {mp3_file.name}")
                    else:
                        raise FileNotFoundError(f"MP3 dosyası oluşturulamadı: {video_id}")
                
                file_size = mp3_file.stat().st_size
                logger.info(f"İndirme tamamlandı: {mp3_file.name} ({file_size} bytes)")
                
                # Base URL
                base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
                audio_url = f"{base_url}/downloads/{mp3_file.name}"
                
                return {
                    "status": "ok",
                    "cached": False,
                    "title": title,
                    "duration": duration,
                    "file_size": file_size,
                    "audio_url": audio_url,
                    "video_id": video_id
                }
                
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                logger.error(f"yt-dlp hatası: {error_msg}")
                
                if "Sign in" in error_msg or "bot" in error_msg.lower():
                    raise HTTPException(
                        status_code=403,
                        detail="YouTube bot koruması aktif. Cookie güncellemesi gerekli."
                    )
                elif "Video unavailable" in error_msg or "Private video" in error_msg:
                    raise HTTPException(
                        status_code=404,
                        detail="Video bulunamadı, özel veya kaldırılmış olabilir"
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"İndirme hatası: {error_msg[:200]}"
                    )
    
    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.error(f"Dosya hatası: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="MP3 dönüştürme başarısız. FFmpeg kurulu değil veya çalışmıyor."
        )
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Sunucu hatası: {str(e)}")

@app.get("/list")
async def list_files():
    """İndirilen MP3 dosyalarını listele"""
    try:
        files = []
        for file in DOWNLOADS_DIR.glob("*.mp3"):
            files.append({
                "filename": file.name,
                "size": file.stat().st_size,
                "size_mb": round(file.stat().st_size / (1024 * 1024), 2),
                "url": f"/downloads/{file.name}"
            })
        
        return {
            "status": "ok",
            "count": len(files),
            "files": sorted(files, key=lambda x: x["filename"])
        }
    except Exception as e:
        logger.error(f"Liste hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/clear")
async def clear_downloads():
    """Tüm indirilen dosyaları sil (TESTİNG için)"""
    try:
        deleted = 0
        for file in DOWNLOADS_DIR.glob("*.mp3"):
            file.unlink()
            deleted += 1
        
        logger.info(f"{deleted} dosya silindi")
        
        return {
            "status": "ok",
            "message": f"{deleted} dosya silindi"
        }
    except Exception as e:
        logger.error(f"Silme hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("YouTube MP3 API Başlatıldı")
    logger.info(f"Downloads klasörü: {DOWNLOADS_DIR.absolute()}")
    logger.info(f"Cookie dosyası: {COOKIES_FILE.absolute()}")
    logger.info(f"Cookie mevcut: {COOKIES_FILE.exists()}")
    logger.info("=" * 50)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Sunucu başlatılıyor: 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

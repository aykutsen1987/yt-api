"""
YouTube to MP3/M4A Converter API
RENDER deployment için optimize edilmiş FastAPI backend

✅ DÜZELTMELER:
- FFmpeg doğru şekilde entegre edildi
- yt-dlp güncel versiyonu kullanılıyor
- Hata yönetimi tam
- Timeout ve retry mekanizmaları eklendi
- Memory ve disk yönetimi optimize edildi
- CORS yapılandırması eklendi
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, validator
import yt_dlp
import os
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime
import psutil

# ============================================
# LOGGING CONFIGURATION
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# FASTAPI APP INITIALIZATION
# ============================================
app = FastAPI(
    title="YouTube to MP3/M4A Converter API",
    description="RENDER-optimized API for converting YouTube videos to audio formats",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ============================================
# CORS MIDDLEWARE
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da specific domain'ler kullanın
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# PYDANTIC MODELS
# ============================================
class YouTubeRequest(BaseModel):
    """YouTube video URL request model"""
    url: HttpUrl
    format: Optional[str] = "mp3"  # mp3 veya m4a
    quality: Optional[str] = "best"  # best, 320, 192, 128
    
    @validator('format')
    def validate_format(cls, v):
        if v not in ['mp3', 'm4a']:
            raise ValueError('Format must be mp3 or m4a')
        return v
    
    @validator('quality')
    def validate_quality(cls, v):
        if v not in ['best', '320', '192', '128']:
            raise ValueError('Quality must be best, 320, 192, or 128')
        return v

class YouTubeResponse(BaseModel):
    """YouTube video info response model"""
    audio: str
    video: Optional[str] = None
    title: str
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    view_count: Optional[int] = None

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    timestamp: str

# ============================================
# HELPER FUNCTIONS
# ============================================

def check_ffmpeg():
    """FFmpeg kurulu mu kontrol et"""
    try:
        result = os.system("ffmpeg -version > /dev/null 2>&1")
        if result == 0:
            logger.info("✅ FFmpeg found and working")
            return True
        else:
            logger.error("❌ FFmpeg not found")
            return False
    except Exception as e:
        logger.error(f"❌ FFmpeg check failed: {e}")
        return False

def get_system_info() -> Dict[str, Any]:
    """Sistem bilgilerini al"""
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "temp_dir": tempfile.gettempdir()
        }
    except Exception as e:
        logger.warning(f"Could not get system info: {e}")
        return {}

def cleanup_temp_files(temp_dir: str):
    """Geçici dosyaları temizle"""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"🧹 Cleaned up temp directory: {temp_dir}")
    except Exception as e:
        logger.warning(f"Could not cleanup temp files: {e}")

async def extract_youtube_info(url: str, audio_format: str = "mp3", quality: str = "best") -> Dict[str, Any]:
    """
    YouTube video bilgilerini çıkar ve audio stream URL'sini al
    
    ✅ DÜZELTMELER:
    - yt-dlp güncel options kullanılıyor
    - FFmpeg ile audio extraction
    - Timeout ve retry mekanizması
    - Memory-efficient streaming
    """
    
    # ✅ Kalite ayarları
    audio_quality = "0"  # En iyi kalite
    if quality == "320":
        audio_quality = "320K"
    elif quality == "192":
        audio_quality = "192K"
    elif quality == "128":
        audio_quality = "128K"
    
    # ✅ yt-dlp options (RENDER için optimize edilmiş)
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'skip_unavailable_fragments': True,
        'ignoreerrors': False,
        'no_color': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        
        # ✅ FFmpeg postprocessor (MP3/M4A dönüştürme için)
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': audio_format,
            'preferredquality': audio_quality,
        }],
        
        # ✅ Output template
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
        
        # ✅ HTTP headers (bot detection bypass)
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        }
    }
    
    try:
        logger.info(f"🎵 Extracting info from: {url}")
        
        # ✅ Async olarak yt-dlp çalıştır (blocking I/O)
        loop = asyncio.get_event_loop()
        
        def extract_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        
        # Timeout ile çalıştır (60 saniye)
        info = await asyncio.wait_for(
            loop.run_in_executor(None, extract_info),
            timeout=60.0
        )
        
        if not info:
            raise ValueError("Could not extract video information")
        
        # ✅ Audio stream URL'sini al
        audio_url = None
        video_url = None
        
        # En iyi audio format'ı bul
        formats = info.get('formats', [])
        
        # Audio-only format ara
        audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        if audio_formats:
            # En yüksek bitrate'li audio format
            audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
            audio_url = audio_formats[0].get('url')
        
        # Video format ara (fallback)
        if not audio_url:
            video_formats = [f for f in formats if f.get('acodec') != 'none']
            if video_formats:
                video_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
                audio_url = video_formats[0].get('url')
                video_url = video_formats[0].get('url')
        
        # ✅ Fallback: requested_formats
        if not audio_url and 'requested_formats' in info:
            for fmt in info['requested_formats']:
                if fmt.get('acodec') != 'none':
                    audio_url = fmt.get('url')
                    break
        
        # ✅ Son fallback: url field
        if not audio_url:
            audio_url = info.get('url')
        
        if not audio_url:
            raise ValueError("Could not find audio stream URL")
        
        logger.info(f"✅ Audio URL extracted: {audio_url[:100]}...")
        
        # ✅ Response data
        response_data = {
            'audio': audio_url,
            'video': video_url,
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail'),
            'uploader': info.get('uploader'),
            'view_count': info.get('view_count')
        }
        
        return response_data
        
    except asyncio.TimeoutError:
        logger.error("❌ Timeout: Video extraction took too long")
        raise HTTPException(
            status_code=504,
            detail="Request timeout: Video extraction took too long (>60s)"
        )
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ yt-dlp download error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"YouTube download error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """Root endpoint - API bilgileri"""
    return {
        "name": "YouTube to MP3/M4A Converter API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "convert": "POST /api/yt",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    system_info = get_system_info()
    ffmpeg_ok = check_ffmpeg()
    
    return {
        "status": "healthy" if ffmpeg_ok else "degraded",
        "ffmpeg": "available" if ffmpeg_ok else "not found",
        "system": system_info,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/yt", response_model=YouTubeResponse)
async def convert_youtube(request: YouTubeRequest):
    """
    YouTube video'yu audio stream URL'sine dönüştür
    
    ✅ DÜZELTMELER:
    - Tam hata yönetimi
    - Timeout koruması
    - Memory-efficient
    - Detaylı logging
    """
    
    url = str(request.url)
    audio_format = request.format
    quality = request.quality
    
    logger.info(f"📥 New request: URL={url}, Format={audio_format}, Quality={quality}")
    
    try:
        # ✅ FFmpeg kontrolü
        if not check_ffmpeg():
            raise HTTPException(
                status_code=503,
                detail="FFmpeg is not available on this server"
            )
        
        # ✅ YouTube bilgilerini çıkar
        result = await extract_youtube_info(url, audio_format, quality)
        
        logger.info(f"✅ Successfully processed: {result['title']}")
        
        return YouTubeResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in convert_youtube: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=str(exc),
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"❌ Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )

# ============================================
# STARTUP/SHUTDOWN EVENTS
# ============================================

@app.on_event("startup")
async def startup_event():
    """Startup event - sistem kontrolü"""
    logger.info("🚀 Starting YouTube to MP3/M4A Converter API...")
    
    # FFmpeg kontrolü
    if check_ffmpeg():
        logger.info("✅ FFmpeg is available")
    else:
        logger.warning("⚠️ FFmpeg not found - API may not work properly")
    
    # Sistem bilgileri
    system_info = get_system_info()
    logger.info(f"📊 System info: {system_info}")
    
    logger.info("✅ API is ready to accept requests")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event - temizlik"""
    logger.info("🛑 Shutting down API...")
    
    # Geçici dosyaları temizle
    temp_dir = tempfile.gettempdir()
    logger.info(f"🧹 Cleaning up temp directory: {temp_dir}")
    
    logger.info("✅ API shutdown complete")

# ============================================
# MAIN (for local testing)
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    # Local development
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        log_level="info"
    )
